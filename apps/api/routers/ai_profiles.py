import datetime
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import AuthenticatedUser, get_current_user
from db import get_conn
from encryption import encrypt_api_key, get_key_id
from models import AIProfileCreate, AIProfileListResponse, AIProfileResponse

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
                "INSERT INTO ai_profiles (user_id, display_name, provider, api_key_ciphertext, api_key_key_id, style) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING id, display_name, provider, style, active, created_at",
                (user_db_id, body.display_name, body.provider, ciphertext, key_id, body.style),
            )
            profile = await cur.fetchone()
            if profile is None:
                raise _error_envelope(request, "INTERNAL_ERROR", "Failed to create profile", 500)

            response_data = {
                "id": str(profile["id"]),
                "display_name": profile["display_name"],
                "provider": profile["provider"],
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
                "SELECT id, display_name, provider, style, active, created_at "
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
                        "style": r["style"],
                        "active": r["active"],
                        "created_at": r["created_at"],
                    }
                    for r in rows
                ]
            }
