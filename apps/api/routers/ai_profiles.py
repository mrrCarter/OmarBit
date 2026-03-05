import datetime
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from auth import AuthenticatedUser, get_current_user
from db import get_conn
from encryption import encrypt_api_key, get_key_id
from models import AIProfileCreate, AIProfileListResponse, AIProfileResponse
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
