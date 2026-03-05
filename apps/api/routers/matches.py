import datetime
import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from auth import AuthenticatedUser, get_current_user
from db import get_conn
from match_engine import can_transition

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["matches"])


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


def _request_hash(body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@router.post("/matches", status_code=201)
async def start_match(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JSONResponse:
    idempotency_key = request.headers.get("idempotency-key")
    if not idempotency_key:
        raise _error_envelope(request, "MISSING_IDEMPOTENCY_KEY", "Idempotency-Key header is required", 400)

    body = await request.json()
    white_ai_id = body.get("white_ai_id")
    black_ai_id = body.get("black_ai_id")
    time_control = body.get("time_control", "5+0")

    if not white_ai_id or not black_ai_id:
        raise _error_envelope(request, "BAD_REQUEST", "white_ai_id and black_ai_id are required", 400)
    if white_ai_id == black_ai_id:
        raise _error_envelope(request, "BAD_REQUEST", "white_ai_id and black_ai_id must differ", 400)

    req_hash = _request_hash({"white_ai_id": white_ai_id, "black_ai_id": black_ai_id})

    async with get_conn() as conn:
        async with conn.cursor() as cur:
            # Resolve user
            await cur.execute("SELECT id FROM users WHERE github_id = %s", (user.github_id,))
            user_row = await cur.fetchone()
            if not user_row:
                raise _error_envelope(request, "UNAUTHORIZED", "User not found", 401)
            user_db_id = user_row["id"]

            # Check idempotency
            await cur.execute(
                "SELECT response_json, status_code, request_hash "
                "FROM idempotency_keys "
                "WHERE actor_id = %s AND key = %s AND endpoint = %s",
                (user_db_id, idempotency_key, "POST /api/v1/matches"),
            )
            existing = await cur.fetchone()
            if existing:
                if existing["request_hash"] != req_hash:
                    raise _error_envelope(
                        request, "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key reused with different request body", 409,
                    )
                return JSONResponse(
                    status_code=existing["status_code"],
                    content=existing["response_json"],
                )

            # Verify both AIs exist and belong to the user
            await cur.execute(
                "SELECT id FROM ai_profiles WHERE id = ANY(%s) AND user_id = %s",
                ([white_ai_id, black_ai_id], user_db_id),
            )
            owned = await cur.fetchall()
            owned_ids = {str(r["id"]) for r in owned}

            # AIs can belong to different users in a real match, but the
            # initiator must own at least one side
            if white_ai_id not in owned_ids and black_ai_id not in owned_ids:
                raise _error_envelope(
                    request, "FORBIDDEN",
                    "You must own at least one AI in the match", 403,
                )

            # Create the match
            await cur.execute(
                "INSERT INTO matches (white_ai_id, black_ai_id, time_control, status) "
                "VALUES (%s, %s, %s, 'scheduled') "
                "RETURNING id, white_ai_id, black_ai_id, time_control, status, created_at",
                (white_ai_id, black_ai_id, time_control),
            )
            match = await cur.fetchone()
            if match is None:
                raise _error_envelope(request, "INTERNAL_ERROR", "Failed to create match", 500)

            response_data = {
                "id": str(match["id"]),
                "white_ai_id": str(match["white_ai_id"]),
                "black_ai_id": str(match["black_ai_id"]),
                "time_control": match["time_control"],
                "status": match["status"],
                "created_at": match["created_at"].isoformat(),
            }

            # Store idempotency key
            await cur.execute(
                "INSERT INTO idempotency_keys "
                "(key, actor_id, endpoint, request_hash, response_json, status_code, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, now() + interval '24 hours')",
                (
                    idempotency_key, user_db_id, "POST /api/v1/matches",
                    req_hash, json.dumps(response_data), 201,
                ),
            )
            await conn.commit()

            # Dispatch match to Celery worker
            _dispatch_match(response_data["id"])

            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            return JSONResponse(
                status_code=201,
                content=response_data,
                headers={"x-request-id": request_id},
            )


def _dispatch_match(match_id: str) -> None:
    """Send match to Celery worker for execution. Best-effort — failures logged.

    Uses send_task() to avoid importing workers module (separate package in monorepo).
    """
    try:
        import os

        from celery import Celery

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        celery_app = Celery(broker=redis_url)
        celery_app.send_task("workers.play_match", args=[match_id])
        logger.info("Dispatched match %s to Celery worker", match_id)
    except Exception as exc:
        logger.error("Failed to dispatch match %s to Celery: %s", match_id, exc)


@router.get("/matches")
async def list_matches(request: Request) -> JSONResponse:
    """List recent matches. Intentionally public (spectator-friendly)."""
    try:
        limit = min(max(1, int(request.query_params.get("limit", "20"))), 100)
    except (ValueError, TypeError):
        limit = 20
    try:
        offset = max(0, int(request.query_params.get("offset", "0")))
    except (ValueError, TypeError):
        offset = 0
    status_filter = request.query_params.get("status")

    async with get_conn() as conn:
        async with conn.cursor() as cur:
            if status_filter:
                await cur.execute(
                    "SELECT m.id, m.white_ai_id, m.black_ai_id, m.time_control, "
                    "m.status, m.winner_ai_id, m.created_at, m.completed_at, "
                    "w.display_name AS white_name, b.display_name AS black_name "
                    "FROM matches m "
                    "JOIN ai_profiles w ON m.white_ai_id = w.id "
                    "JOIN ai_profiles b ON m.black_ai_id = b.id "
                    "WHERE m.status = %s "
                    "ORDER BY m.created_at DESC LIMIT %s OFFSET %s",
                    (status_filter, limit, offset),
                )
            else:
                await cur.execute(
                    "SELECT m.id, m.white_ai_id, m.black_ai_id, m.time_control, "
                    "m.status, m.winner_ai_id, m.created_at, m.completed_at, "
                    "w.display_name AS white_name, b.display_name AS black_name "
                    "FROM matches m "
                    "JOIN ai_profiles w ON m.white_ai_id = w.id "
                    "JOIN ai_profiles b ON m.black_ai_id = b.id "
                    "ORDER BY m.created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset),
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


@router.post("/matches/{match_id}/forfeit")
async def forfeit_match(
    match_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JSONResponse:
    idempotency_key = request.headers.get("idempotency-key")
    if not idempotency_key:
        raise _error_envelope(request, "MISSING_IDEMPOTENCY_KEY", "Idempotency-Key header is required", 400)

    body = await request.json()
    reason = body.get("reason", "Manual forfeit")

    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, status, white_ai_id, black_ai_id FROM matches WHERE id = %s",
                (match_id,),
            )
            match = await cur.fetchone()
            if not match:
                raise _error_envelope(request, "NOT_FOUND", "Match not found", 404)

            if not can_transition(match["status"], "forfeit"):
                raise _error_envelope(
                    request, "INVALID_STATE",
                    f"Cannot forfeit match in '{match['status']}' state", 409,
                )

            await cur.execute(
                "UPDATE matches SET status = 'forfeit', forfeit_reason = %s, "
                "completed_at = now() WHERE id = %s "
                "RETURNING id, status, forfeit_reason, completed_at",
                (reason, match_id),
            )
            updated = await cur.fetchone()
            await conn.commit()

            if updated is None:
                raise _error_envelope(request, "INTERNAL_ERROR", "Failed to forfeit match", 500)

            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            return JSONResponse(
                status_code=200,
                content={
                    "id": str(updated["id"]),
                    "status": updated["status"],
                    "forfeit_reason": updated["forfeit_reason"],
                    "completed_at": updated["completed_at"].isoformat(),
                },
                headers={"x-request-id": request_id},
            )


@router.post("/matches/{match_id}/start")
async def retry_start_match(
    match_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JSONResponse:
    """Re-dispatch a scheduled match to the Celery worker."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, status, white_ai_id, black_ai_id FROM matches WHERE id = %s",
                (match_id,),
            )
            match = await cur.fetchone()
            if not match:
                raise _error_envelope(request, "NOT_FOUND", "Match not found", 404)
            if match["status"] != "scheduled":
                raise _error_envelope(
                    request, "INVALID_STATE",
                    f"Match is '{match['status']}', can only start 'scheduled' matches", 409,
                )

            _dispatch_match(str(match["id"]))

            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            return JSONResponse(
                status_code=200,
                content={"id": str(match["id"]), "status": "dispatched"},
                headers={"x-request-id": request_id},
            )


@router.get("/matches/{match_id}")
async def get_match(match_id: str, request: Request) -> JSONResponse:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, white_ai_id, black_ai_id, time_control, status, "
                "winner_ai_id, forfeit_reason, pgn, created_at, completed_at "
                "FROM matches WHERE id = %s",
                (match_id,),
            )
            match = await cur.fetchone()
            if not match:
                raise _error_envelope(request, "NOT_FOUND", "Match not found", 404)

            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            return JSONResponse(
                status_code=200,
                content={
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
                headers={"x-request-id": request_id},
            )
