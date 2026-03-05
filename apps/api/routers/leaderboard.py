"""Leaderboard API — GET /api/v1/leaderboard.

This endpoint is intentionally public (no auth required) per spec:
spectators and visitors can view the leaderboard without signing in.
"""

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from db import get_conn

router = APIRouter(prefix="/api/v1", tags=["leaderboard"])


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


@router.get("/leaderboard")
async def get_leaderboard(request: Request) -> JSONResponse:
    """Return top AI profiles ranked by ELO rating.

    Query params:
        limit: max results (default 50, clamped 1-100)
        offset: pagination offset (default 0, min 0)
    """
    limit = max(1, min(_parse_int(request.query_params.get("limit", "50"), 50), 100))
    offset = max(0, _parse_int(request.query_params.get("offset", "0"), 0))

    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT e.ai_id, e.rating, e.wins, e.losses, e.draws, e.updated_at, "
                "a.display_name, a.provider, a.model, a.style "
                "FROM elo_ratings e "
                "JOIN ai_profiles a ON a.id = e.ai_id "
                "WHERE a.active = true "
                "ORDER BY e.rating DESC, e.wins DESC "
                "LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = await cur.fetchall()

            await cur.execute(
                "SELECT COUNT(*) as total FROM elo_ratings e "
                "JOIN ai_profiles a ON a.id = e.ai_id "
                "WHERE a.active = true"
            )
            count_row = await cur.fetchone()
            total = count_row["total"] if count_row else 0

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=200,
        content={
            "entries": [
                {
                    "ai_id": str(r["ai_id"]),
                    "display_name": r["display_name"],
                    "provider": r["provider"],
                    "model": r.get("model", ""),
                    "style": r["style"],
                    "rating": r["rating"],
                    "wins": r["wins"],
                    "losses": r["losses"],
                    "draws": r["draws"],
                    "updated_at": r["updated_at"].isoformat(),
                }
                for r in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
        headers={"x-request-id": request_id},
    )
