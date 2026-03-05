import asyncio
import json
import uuid as uuid_mod

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from db import get_conn


def _validate_uuid(value: str) -> str:
    """Validate and normalize a UUID string."""
    try:
        return str(uuid_mod.UUID(value))
    except ValueError:
        raise ValueError(f"Invalid UUID: {value[:50]}")

router = APIRouter(prefix="/api/v1", tags=["sse"])


async def _match_event_generator(match_id: str, request: Request):
    """SSE generator for match events.

    Polls the match_moves table for new moves and yields them as SSE events.
    Also yields match status changes (completion, forfeit, abort).
    """
    last_ply = -1

    while True:
        if await request.is_disconnected():
            break

        try:
            async with get_conn() as conn:
                async with conn.cursor() as cur:
                    # Check match status
                    await cur.execute(
                        "SELECT status, winner_ai_id, forfeit_reason, completed_at "
                        "FROM matches WHERE id = %s",
                        (match_id,),
                    )
                    match = await cur.fetchone()
                    if not match:
                        yield _sse_event("error", {"message": "Match not found"})
                        break

                    # Fetch new moves since last_ply
                    await cur.execute(
                        "SELECT ply, san, fen, stockfish_eval_cp, think_summary, chat_line, created_at "
                        "FROM match_moves WHERE match_id = %s AND ply > %s "
                        "ORDER BY ply LIMIT 50",
                        (match_id, last_ply),
                    )
                    moves = await cur.fetchall()

                    for move in moves:
                        last_ply = move["ply"]
                        yield _sse_event("move", {
                            "ply": move["ply"],
                            "san": move["san"],
                            "fen": move["fen"],
                            "eval_cp": move["stockfish_eval_cp"],
                            "think_summary": move["think_summary"],
                            "chat_line": move["chat_line"],
                            "timestamp": move["created_at"].isoformat(),
                        })

                    # Emit status if terminal
                    if match["status"] in ("completed", "forfeit", "aborted"):
                        yield _sse_event("match_end", {
                            "status": match["status"],
                            "winner_ai_id": str(match["winner_ai_id"]) if match["winner_ai_id"] else None,
                            "forfeit_reason": match["forfeit_reason"],
                            "completed_at": match["completed_at"].isoformat() if match["completed_at"] else None,
                        })
                        break

        except RuntimeError:
            # DB pool not available
            yield _sse_event("error", {"message": "Service temporarily unavailable"})
            break

        # Poll interval: 1 second
        await asyncio.sleep(1)


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream/matches/{match_id}")
async def stream_match(match_id: str, request: Request) -> StreamingResponse:
    try:
        match_id = _validate_uuid(match_id)
    except ValueError:
        return StreamingResponse(
            iter([_sse_event("error", {"message": "Invalid match ID"})]),
            media_type="text/event-stream",
        )
    return StreamingResponse(
        _match_event_generator(match_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
