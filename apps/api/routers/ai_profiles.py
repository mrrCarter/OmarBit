import datetime
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from auth import AuthenticatedUser, get_current_user
from db import get_conn
from encryption import encrypt_api_key, get_key_id
from models import AIProfileCreate, AIProfileListResponse, AIProfileResponse, AIProfileUpdate
from providers.key_validator import validate_api_key
from providers.models import get_default_model, is_valid_model

router = APIRouter(prefix="/api/v1", tags=["ai-profiles"])


def _error_envelope(request: Request, code: str, message: str, status: int) -> HTTPException:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return HTTPException(
        status_code=status,
        detail={
            "error": {"code": code, "message": message},
            "requestId": request_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    )


def _compute_request_hash(body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@router.get("/providers/models")
async def list_provider_models() -> JSONResponse:
    """Return available models per provider with cost info."""
    from providers.models import MODELS

    result = {}
    for provider, models in MODELS.items():
        result[provider] = [
            {
                "id": m.id,
                "name": m.name,
                "cost_per_1m_input": m.cost_per_1m_input,
                "cost_per_1m_output": m.cost_per_1m_output,
            }
            for m in models
        ]
    return JSONResponse(content=result)


@router.post("/ai-profiles", response_model=AIProfileResponse, status_code=201)
async def create_ai_profile(
    body: AIProfileCreate,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    # Idempotency-Key required for mutations
    idempotency_key = request.headers.get("idempotency-key")
    if not idempotency_key:
        raise _error_envelope(request, "MISSING_IDEMPOTENCY_KEY", "Idempotency-Key header is required", 400)

    # Resolve model — use default if not specified
    model = body.model or get_default_model(body.provider)
    if model and not is_valid_model(body.provider, model):
        raise _error_envelope(
            request, "INVALID_MODEL",
            f"Model '{model}' is not available for provider '{body.provider}'", 400,
        )

    # Validate API key with a test call
    key_valid, key_error = await validate_api_key(body.provider, model, body.api_key)
    if not key_valid:
        raise _error_envelope(request, "INVALID_API_KEY", key_error, 400)

    # Sanitize custom instructions (strip code blocks, URLs, injection patterns)
    sanitized_instructions = body.custom_instructions
    if sanitized_instructions:
        from instruction_sanitizer import sanitize_instructions

        sanitized_instructions, sanitize_warnings = sanitize_instructions(sanitized_instructions)
        for w in sanitize_warnings:
            if w.startswith("REJECTED:"):
                raise _error_envelope(
                    request, "UNSAFE_INSTRUCTIONS",
                    f"Custom instructions rejected: {w.removeprefix('REJECTED: ')}", 400,
                )

        # Run LLM safety scanner (feature-flagged, non-blocking on failure)
        from safety_scanner import scan_instructions

        is_safe, safety_reason = await scan_instructions(sanitized_instructions)
        if not is_safe:
            raise _error_envelope(
                request, "UNSAFE_INSTRUCTIONS",
                f"Custom instructions flagged by safety review: {safety_reason}", 400,
            )

    request_hash = _compute_request_hash(body.model_dump(exclude={"api_key"}))

    async with get_conn() as conn:
        async with conn.cursor() as cur:
            # Ensure user exists in DB (upsert from OAuth)
            await cur.execute(
                "INSERT INTO users (github_id, username) VALUES (%s, %s) "
                "ON CONFLICT (github_id) DO UPDATE SET username = EXCLUDED.username "
                "RETURNING id",
                (user.github_id, user.username),
            )
            user_row = await cur.fetchone()
            if user_row is None:
                raise _error_envelope(request, "INTERNAL_ERROR", "Failed to resolve user", 500)
            user_db_id = user_row["id"]

            # Check idempotency
            await cur.execute(
                "SELECT response_json, status_code FROM idempotency_keys "
                "WHERE actor_id = %s AND key = %s AND endpoint = %s",
                (user_db_id, idempotency_key, "POST /api/v1/ai-profiles"),
            )
            existing = await cur.fetchone()
            if existing:
                # Check request hash match
                await cur.execute(
                    "SELECT request_hash FROM idempotency_keys "
                    "WHERE actor_id = %s AND key = %s AND endpoint = %s",
                    (user_db_id, idempotency_key, "POST /api/v1/ai-profiles"),
                )
                hash_row = await cur.fetchone()
                if hash_row and hash_row["request_hash"] != request_hash:
                    raise _error_envelope(
                        request, "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key reused with different request body", 409
                    )
                # Replay stored response
                return existing["response_json"]

            # Encrypt the API key
            ciphertext = encrypt_api_key(body.api_key)
            key_id = get_key_id()

            # Insert AI profile
            await cur.execute(
                "INSERT INTO ai_profiles "
                "(user_id, display_name, provider, model, api_key_ciphertext, api_key_key_id, "
                "style, custom_instructions) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id, display_name, provider, model, style, active, created_at",
                (
                    user_db_id, body.display_name, body.provider, model,
                    ciphertext, key_id, body.style, sanitized_instructions,
                ),
            )
            profile = await cur.fetchone()
            if profile is None:
                raise _error_envelope(request, "INTERNAL_ERROR", "Failed to create profile", 500)

            response_data = {
                "id": str(profile["id"]),
                "display_name": profile["display_name"],
                "provider": profile["provider"],
                "model": profile["model"],
                "style": profile["style"],
                "active": profile["active"],
                "created_at": profile["created_at"].isoformat(),
            }

            # Store idempotency key (24h TTL)
            await cur.execute(
                "INSERT INTO idempotency_keys "
                "(key, actor_id, endpoint, request_hash, response_json, status_code, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, now() + interval '24 hours')",
                (
                    idempotency_key, user_db_id, "POST /api/v1/ai-profiles",
                    request_hash, json.dumps(response_data), 201,
                ),
            )

            # Initialize ELO rating
            await cur.execute(
                "INSERT INTO elo_ratings (ai_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (profile["id"],),
            )

            await conn.commit()
            return response_data


@router.get("/ai-profiles/me", response_model=AIProfileListResponse)
async def list_my_profiles(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            # Resolve user
            await cur.execute("SELECT id FROM users WHERE github_id = %s", (user.github_id,))
            user_row = await cur.fetchone()
            if not user_row:
                return {"profiles": []}

            await cur.execute(
                "SELECT id, display_name, provider, model, style, active, created_at "
                "FROM ai_profiles WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
                (user_row["id"],),
            )
            rows = await cur.fetchall()
            return {
                "profiles": [
                    {
                        "id": str(r["id"]),
                        "display_name": r["display_name"],
                        "provider": r["provider"],
                        "model": r.get("model", ""),
                        "style": r["style"],
                        "active": r["active"],
                        "created_at": r["created_at"],
                    }
                    for r in rows
                ]
            }


@router.patch("/ai-profiles/{profile_id}", response_model=AIProfileResponse)
async def update_ai_profile(
    profile_id: str,
    body: AIProfileUpdate,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Update an AI profile. Only the owner can update."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            # Resolve user
            await cur.execute("SELECT id FROM users WHERE github_id = %s", (user.github_id,))
            user_row = await cur.fetchone()
            if not user_row:
                raise _error_envelope(request, "UNAUTHORIZED", "User not found", 401)

            # Load profile and verify ownership
            await cur.execute(
                "SELECT id, user_id, provider, model FROM ai_profiles WHERE id = %s",
                (profile_id,),
            )
            profile = await cur.fetchone()
            if not profile:
                raise _error_envelope(request, "NOT_FOUND", "AI profile not found", 404)
            if profile["user_id"] != user_row["id"]:
                raise _error_envelope(request, "FORBIDDEN", "You do not own this profile", 403)

            # Validate model if changed
            if body.model is not None and body.model != profile["model"]:
                if not is_valid_model(profile["provider"], body.model):
                    raise _error_envelope(
                        request, "INVALID_MODEL",
                        f"Model '{body.model}' is not available for provider '{profile['provider']}'",
                        400,
                    )

            # Sanitize instructions if changed
            sanitized_instructions = body.custom_instructions
            if sanitized_instructions is not None:
                from instruction_sanitizer import sanitize_instructions

                sanitized_instructions, sanitize_warnings = sanitize_instructions(sanitized_instructions)
                for w in sanitize_warnings:
                    if w.startswith("REJECTED:"):
                        raise _error_envelope(
                            request, "UNSAFE_INSTRUCTIONS",
                            f"Custom instructions rejected: {w.removeprefix('REJECTED: ')}",
                            400,
                        )

                from safety_scanner import scan_instructions

                is_safe, safety_reason = await scan_instructions(sanitized_instructions)
                if not is_safe:
                    raise _error_envelope(
                        request, "UNSAFE_INSTRUCTIONS",
                        f"Custom instructions flagged: {safety_reason}", 400,
                    )

            # Build SET clause dynamically
            from psycopg import sql

            set_parts: list[sql.Composable] = []
            params: list = []

            if body.display_name is not None:
                set_parts.append(sql.SQL("display_name = %s"))
                params.append(body.display_name)
            if body.style is not None:
                set_parts.append(sql.SQL("style = %s"))
                params.append(body.style)
            if body.model is not None:
                set_parts.append(sql.SQL("model = %s"))
                params.append(body.model)
            if body.active is not None:
                set_parts.append(sql.SQL("active = %s"))
                params.append(body.active)
            if sanitized_instructions is not None:
                set_parts.append(sql.SQL("custom_instructions = %s"))
                params.append(sanitized_instructions)

            if not set_parts:
                raise _error_envelope(request, "BAD_REQUEST", "No fields to update", 400)

            params.append(profile_id)
            query = sql.SQL(
                "UPDATE ai_profiles SET {} WHERE id = %s "
                "RETURNING id, display_name, provider, model, style, active, created_at"
            ).format(sql.SQL(", ").join(set_parts))

            await cur.execute(query, tuple(params))
            updated = await cur.fetchone()
            await conn.commit()

            if updated is None:
                raise _error_envelope(request, "INTERNAL_ERROR", "Failed to update profile", 500)

            return {
                "id": str(updated["id"]),
                "display_name": updated["display_name"],
                "provider": updated["provider"],
                "model": updated["model"] or "",
                "style": updated["style"],
                "active": updated["active"],
                "created_at": updated["created_at"],
            }


@router.delete("/ai-profiles/{profile_id}", status_code=200)
async def delete_ai_profile(
    profile_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JSONResponse:
    """Soft-delete an AI profile (set active=false). Cannot delete if in active match."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM users WHERE github_id = %s", (user.github_id,))
            user_row = await cur.fetchone()
            if not user_row:
                raise _error_envelope(request, "UNAUTHORIZED", "User not found", 401)

            await cur.execute(
                "SELECT id, user_id FROM ai_profiles WHERE id = %s",
                (profile_id,),
            )
            profile = await cur.fetchone()
            if not profile:
                raise _error_envelope(request, "NOT_FOUND", "AI profile not found", 404)
            if profile["user_id"] != user_row["id"]:
                raise _error_envelope(request, "FORBIDDEN", "You do not own this profile", 403)

            # Check for active matches
            await cur.execute(
                "SELECT id FROM matches "
                "WHERE (white_ai_id = %s OR black_ai_id = %s) "
                "AND status IN ('scheduled', 'in_progress') "
                "LIMIT 1",
                (profile_id, profile_id),
            )
            active_match = await cur.fetchone()
            if active_match:
                raise _error_envelope(
                    request, "CONFLICT",
                    "Cannot delete AI with active matches. Forfeit or wait for completion.",
                    409,
                )

            await cur.execute(
                "UPDATE ai_profiles SET active = false WHERE id = %s", (profile_id,),
            )
            await conn.commit()

            return JSONResponse(
                status_code=200,
                content={"id": str(profile_id), "deleted": True},
            )


@router.get("/ai-profiles/{profile_id}/matches")
async def get_ai_match_history(
    profile_id: str,
    request: Request,
) -> JSONResponse:
    """Return match history for an AI profile. Public endpoint."""
    try:
        limit = min(max(1, int(request.query_params.get("limit", "20"))), 100)
    except (ValueError, TypeError):
        limit = 20
    try:
        offset = max(0, int(request.query_params.get("offset", "0")))
    except (ValueError, TypeError):
        offset = 0

    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT m.id, m.white_ai_id, m.black_ai_id, m.time_control, "
                "m.status, m.winner_ai_id, m.created_at, m.completed_at, "
                "w.display_name AS white_name, b.display_name AS black_name "
                "FROM matches m "
                "JOIN ai_profiles w ON m.white_ai_id = w.id "
                "JOIN ai_profiles b ON m.black_ai_id = b.id "
                "WHERE m.white_ai_id = %s OR m.black_ai_id = %s "
                "ORDER BY m.created_at DESC LIMIT %s OFFSET %s",
                (profile_id, profile_id, limit, offset),
            )
            rows = await cur.fetchall()

            matches = [
                {
                    "id": str(r["id"]),
                    "white_ai_id": str(r["white_ai_id"]),
                    "black_ai_id": str(r["black_ai_id"]),
                    "white_name": r["white_name"],
                    "black_name": r["black_name"],
                    "time_control": r["time_control"],
                    "status": r["status"],
                    "winner_ai_id": str(r["winner_ai_id"]) if r["winner_ai_id"] else None,
                    "created_at": r["created_at"].isoformat(),
                    "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                }
                for r in rows
            ]

            return JSONResponse(status_code=200, content={"matches": matches})
