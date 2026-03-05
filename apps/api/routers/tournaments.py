"""Tournament API — schedule and manage round-robin tournaments.

Requires authentication. Tournament scheduling is gated by the
'tournament_scheduler' feature flag.
"""

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from auth import AuthenticatedUser, get_current_user
from canary import evaluate_rollout
from db import get_conn
from scheduler import schedule_tournament

router = APIRouter(prefix="/api/v1", tags=["tournaments"])


def _error_envelope(request: Request, code: str, message: str, status: int):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    raise HTTPException(
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
    """
    # Check feature flag
    async with get_conn() as conn:
        async with conn.cursor() as cur:
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
        _error_envelope(
            request,
            "FEATURE_DISABLED",
            "Tournament scheduling is not yet available",
            403,
        )

    # Get all active AI profiles
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM ai_profiles WHERE active = true "
                "ORDER BY created_at LIMIT 100"
            )
            rows = await cur.fetchall()

    ai_ids = [str(r["id"]) for r in rows]

    if len(ai_ids) < 2:
        _error_envelope(
            request,
            "INSUFFICIENT_AIS",
            "Need at least 2 active AIs to schedule a tournament",
            400,
        )

    tournament = schedule_tournament(ai_ids)

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=201,
        content=tournament,
        headers={"x-request-id": request_id},
    )
