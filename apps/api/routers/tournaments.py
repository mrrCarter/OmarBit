"""Tournament API — schedule and manage round-robin tournaments.

Requires authentication. Tournament scheduling is gated by the
'tournament_scheduler' feature flag. Idempotency-Key required.
"""

import datetime
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from auth import AuthenticatedUser, get_current_user
from canary import evaluate_rollout
from db import get_conn
from scheduler import schedule_tournament

router = APIRouter(prefix="/api/v1", tags=["tournaments"])

# Cap AI count for round-robin to prevent O(n^2) DoS
_MAX_TOURNAMENT_AIS = 32


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


@router.post("/tournaments/schedule", status_code=201)
async def schedule_tournament_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JSONResponse:
    """Schedule a round-robin tournament for all active AIs.

    Gated by the 'tournament_scheduler' feature flag.
    Requires Idempotency-Key header.
    Max 32 AIs per tournament to bound O(n^2) pairing generation.
    """
    idempotency_key = request.headers.get("idempotency-key")
    if not idempotency_key:
        raise _error_envelope(
            request, "MISSING_IDEMPOTENCY_KEY",
            "Idempotency-Key header is required", 400,
        )

    async with get_conn() as conn:
        async with conn.cursor() as cur:
            # Check feature flag
            await cur.execute(
                "SELECT enabled, rollout_percent FROM feature_flags WHERE key = %s",
                ("tournament_scheduler",),
            )
            flag = await cur.fetchone()

            if not flag or not evaluate_rollout(
                "tournament_scheduler",
                user.id or user.github_id,
                flag["rollout_percent"] if flag else 0,
                flag["enabled"] if flag else False,
            ):
                raise _error_envelope(
                    request,
                    "FEATURE_DISABLED",
                    "Tournament scheduling is not yet available",
                    403,
                )

            # Resolve user
            await cur.execute(
                "SELECT id FROM users WHERE github_id = %s",
                (user.github_id,),
            )
            user_row = await cur.fetchone()
            if not user_row:
                raise _error_envelope(
                    request, "UNAUTHORIZED", "User not found", 401,
                )
            user_db_id = user_row["id"]

            # Check idempotency
            req_hash = hashlib.sha256(b"schedule_tournament").hexdigest()
            await cur.execute(
                "SELECT response_json, status_code, request_hash "
                "FROM idempotency_keys "
                "WHERE actor_id = %s AND key = %s AND endpoint = %s",
                (user_db_id, idempotency_key, "POST /api/v1/tournaments/schedule"),
            )
            existing = await cur.fetchone()
            if existing:
                if existing["request_hash"] != req_hash:
                    raise _error_envelope(
                        request, "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key reused with different request", 409,
                    )
                return JSONResponse(
                    status_code=existing["status_code"],
                    content=existing["response_json"],
                )

            # Get active AI profiles (capped)
            await cur.execute(
                "SELECT id FROM ai_profiles WHERE active = true "
                "ORDER BY created_at LIMIT %s",
                (_MAX_TOURNAMENT_AIS,),
            )
            rows = await cur.fetchall()

    ai_ids = [str(r["id"]) for r in rows]

    if len(ai_ids) < 2:
        raise _error_envelope(
            request,
            "INSUFFICIENT_AIS",
            "Need at least 2 active AIs to schedule a tournament",
            400,
        )

    tournament = schedule_tournament(ai_ids)

    # Persist idempotency key
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO idempotency_keys "
                "(key, actor_id, endpoint, request_hash, response_json, status_code, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, now() + interval '24 hours')",
                (
                    idempotency_key, user_db_id,
                    "POST /api/v1/tournaments/schedule",
                    req_hash, json.dumps(tournament), 201,
                ),
            )
            await conn.commit()

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=201,
        content=tournament,
        headers={"x-request-id": request_id},
    )
