"""Replay API — GET /api/v1/matches/{id}/replay.

This endpoint is intentionally public (no auth required) per spec:
spectators can view replays of completed matches without signing in.
"""

import datetime
import hashlib
import json
import uuid as uuid_mod

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from db import get_conn

router = APIRouter(prefix="/api/v1", tags=["replay"])


def _validate_uuid(value: str) -> str:
    try:
        return str(uuid_mod.UUID(value))
    except ValueError:
        raise ValueError(f"Invalid UUID: {value[:50]}")


def _error_envelope(request: Request, code: str, message: str, status: int):
    request_id = getattr(request.state, "request_id", str(uuid_mod.uuid4()))
    raise HTTPException(
        status_code=status,
        detail={
            "error": {"code": code, "message": message},
            "requestId": request_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    )


@router.get("/matches/{match_id}/replay")
async def get_replay(match_id: str, request: Request) -> JSONResponse:
    """Return full move history for replay.

    Includes a content hash for IndexedDB sync verification.
    """
    try:
        match_id = _validate_uuid(match_id)
    except ValueError:
        _error_envelope(request, "BAD_REQUEST", "Invalid match ID", 400)

    async with get_conn() as conn:
        async with conn.cursor() as cur:
            # Get match info
            await cur.execute(
                "SELECT id, white_ai_id, black_ai_id, time_control, status, "
                "winner_ai_id, forfeit_reason, pgn, created_at, completed_at "
                "FROM matches WHERE id = %s",
                (match_id,),
            )
            match = await cur.fetchone()
            if not match:
                _error_envelope(request, "NOT_FOUND", "Match not found", 404)

            # Get all moves ordered by ply
            await cur.execute(
                "SELECT ply, san, fen, stockfish_eval_cp, think_summary, "
                "chat_line, created_at "
                "FROM match_moves WHERE match_id = %s "
                "ORDER BY ply LIMIT 500",
                (match_id,),
            )
            moves = await cur.fetchall()

    # Build replay data
    moves_data = [
        {
            "ply": m["ply"],
            "san": m["san"],
            "fen": m["fen"],
            "eval_cp": m["stockfish_eval_cp"],
            "think_summary": m["think_summary"],
            "chat_line": m["chat_line"],
            "timestamp": m["created_at"].isoformat(),
        }
        for m in moves
    ]

    # Content hash for IndexedDB sync verification
    content_hash = hashlib.sha256(
        json.dumps(moves_data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    request_id = getattr(request.state, "request_id", str(uuid_mod.uuid4()))
    return JSONResponse(
        status_code=200,
        content={
            "match": {
                "id": str(match["id"]),
                "white_ai_id": str(match["white_ai_id"]),
                "black_ai_id": str(match["black_ai_id"]),
                "time_control": match["time_control"],
                "status": match["status"],
                "winner_ai_id": str(match["winner_ai_id"]) if match["winner_ai_id"] else None,
                "forfeit_reason": match["forfeit_reason"],
                "pgn": match["pgn"],
                "created_at": match["created_at"].isoformat(),
                "completed_at": match["completed_at"].isoformat() if match["completed_at"] else None,
            },
            "moves": moves_data,
            "content_hash": content_hash,
            "move_count": len(moves_data),
        },
        headers={"x-request-id": request_id},
    )
