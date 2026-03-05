import asyncio
import json
import logging
import os
import uuid as uuid_mod

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from db import get_conn

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _validate_uuid(value: str) -> str:
    """Validate and normalize a UUID string."""
    try:
        return str(uuid_mod.UUID(value))
    except ValueError:
        raise ValueError(f"Invalid UUID: {value[:50]}")


router = APIRouter(prefix="/api/v1", tags=["sse"])


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def _redis_event_generator(match_id: str, request: Request):
    """SSE generator using Redis pub/sub for real-time match events.

    Falls back to DB polling if Redis is unavailable.
    """
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"match:{match_id}")

        # First, send any existing moves (catch-up for late joiners)
        async for event in _catchup_moves(match_id):
            yield event

        # Then listen for real-time events
        while True:
            if await request.is_disconnected():
                break

            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0,
            )
            if message and message["type"] == "message":
                payload = json.loads(message["data"])
                event_type = payload.get("event", "update")
                event_data = payload.get("data", {})
                yield _sse_event(event_type, event_data)

                if event_type == "match_end":
                    break

            await asyncio.sleep(0.1)

        await pubsub.unsubscribe(f"match:{match_id}")
        await r.aclose()

    except Exception as exc:
        logger.warning("Redis pub/sub failed, falling back to polling: %s", exc)
        async for event in _polling_event_generator(match_id, request):
            yield event


async def _catchup_moves(match_id: str):
    """Yield existing moves for a match (for late-joining spectators)."""
    try:
        async with get_conn() as conn:
            async with conn.cursor() as cur:
                # Check match exists and get status
                await cur.execute(
                    "SELECT status, winner_ai_id, forfeit_reason, completed_at "
                    "FROM matches WHERE id = %s",
                    (match_id,),
                )
                match = await cur.fetchone()
                if not match:
                    yield _sse_event("error", {"message": "Match not found"})
                    return

                # Send existing moves
                await cur.execute(
                    "SELECT ply, san, fen, stockfish_eval_cp, think_summary, "
                    "chat_line, created_at "
                    "FROM match_moves WHERE match_id = %s "
                    "ORDER BY ply LIMIT 500",
                    (match_id,),
                )
                moves = await cur.fetchall()
                for move in moves:
                    yield _sse_event("move", {
                        "ply": move["ply"],
                        "san": move["san"],
                        "fen": move["fen"],
                        "eval_cp": move["stockfish_eval_cp"],
                        "think_summary": move["think_summary"],
                        "chat_line": move["chat_line"],
                        "timestamp": move["created_at"].isoformat(),
                    })

                # If already terminal, send match_end
                if match["status"] in ("completed", "forfeit", "aborted"):
                    yield _sse_event("match_end", {
                        "status": match["status"],
                        "winner_ai_id": (
                            str(match["winner_ai_id"]) if match["winner_ai_id"] else None
                        ),
                        "forfeit_reason": match["forfeit_reason"],
                        "completed_at": (
                            match["completed_at"].isoformat() if match["completed_at"] else None
                        ),
                    })
    except RuntimeError:
        yield _sse_event("error", {"message": "Service temporarily unavailable"})


async def _polling_event_generator(match_id: str, request: Request):
    """Fallback SSE generator using DB polling."""
    last_ply = -1

    while True:
        if await request.is_disconnected():
            break

        try:
            async with get_conn() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT status, winner_ai_id, forfeit_reason, completed_at "
                        "FROM matches WHERE id = %s",
                        (match_id,),
                    )
                    match = await cur.fetchone()
                    if not match:
                        yield _sse_event("error", {"message": "Match not found"})
                        break

                    await cur.execute(
                        "SELECT ply, san, fen, stockfish_eval_cp, think_summary, "
                        "chat_line, created_at "
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

                    if match["status"] in ("completed", "forfeit", "aborted"):
                        yield _sse_event("match_end", {
                            "status": match["status"],
                            "winner_ai_id": (
                                str(match["winner_ai_id"]) if match["winner_ai_id"] else None
                            ),
                            "forfeit_reason": match["forfeit_reason"],
                            "completed_at": (
                                match["completed_at"].isoformat()
                                if match["completed_at"] else None
                            ),
                        })
                        break
        except RuntimeError:
            yield _sse_event("error", {"message": "Service temporarily unavailable"})
            break

        await asyncio.sleep(1)


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
        _redis_event_generator(match_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
