"""Core game loop — plays a match from start to finish.

This is the beating heart of OmarBit. It:
1. Transitions match from scheduled -> in_progress
2. Loops turns: provider -> stockfish validation -> moderation -> persist move
3. Tracks clocks (5+0 blitz)
4. Detects game-over (checkmate, stalemate, draw rules)
5. Updates ELO transactionally on completion
6. Publishes SSE events via Redis pub/sub
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

import chess
import chess.pgn

from db import get_conn
from elo import DEFAULT_RATING, calculate_new_ratings
from encryption import decrypt_api_key
from match_engine import can_transition
from move_orchestrator import orchestrate_move
from stockfish import evaluate_position

logger = logging.getLogger(__name__)

# 5+0 blitz: 300 seconds per side, 0 increment
_INITIAL_TIME_SEC = 300.0
_INCREMENT_SEC = 0.0

# Max plies before declaring a draw (prevents infinite games)
MAX_PLIES = 300


@dataclass
class MatchClock:
    """Tracks time remaining for each side."""

    white_time: float = _INITIAL_TIME_SEC
    black_time: float = _INITIAL_TIME_SEC
    active_side: chess.Color = chess.WHITE
    last_move_timestamp: float = field(default_factory=time.monotonic)

    def start_turn(self) -> None:
        self.last_move_timestamp = time.monotonic()

    def end_turn(self) -> float:
        """Record elapsed time for the active side. Returns time consumed."""
        elapsed = time.monotonic() - self.last_move_timestamp
        if self.active_side == chess.WHITE:
            self.white_time -= elapsed
            self.white_time += _INCREMENT_SEC
        else:
            self.black_time -= elapsed
            self.black_time += _INCREMENT_SEC
        self.active_side = not self.active_side
        return elapsed

    def is_flagged(self) -> bool:
        """Check if the active side has run out of time."""
        return self.active_remaining() <= 0

    def active_remaining(self) -> float:
        elapsed = time.monotonic() - self.last_move_timestamp
        if self.active_side == chess.WHITE:
            return max(0.0, self.white_time - elapsed)
        return max(0.0, self.black_time - elapsed)


def parse_time_control(tc: str) -> tuple[float, float]:
    """Parse time control string like '5+0' into (initial_sec, increment_sec)."""
    parts = tc.split("+")
    if len(parts) == 2:
        try:
            return float(parts[0]) * 60, float(parts[1])
        except ValueError:
            pass
    return _INITIAL_TIME_SEC, _INCREMENT_SEC


async def _publish_event(match_id: str, event_type: str, data: dict) -> None:
    """Publish SSE event via Redis pub/sub."""
    try:
        import os

        import redis.asyncio as aioredis

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url, decode_responses=True)
        channel = f"match:{match_id}"
        payload = json.dumps({"event": event_type, "data": data})
        await r.publish(channel, payload)
        await r.aclose()
    except Exception as exc:
        logger.warning("Failed to publish SSE event: %s", exc)


async def _load_match(match_id: str) -> dict | None:
    """Load match record from DB."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, white_ai_id, black_ai_id, time_control, status "
                "FROM matches WHERE id = %s",
                (match_id,),
            )
            return await cur.fetchone()


async def _load_ai_profile(ai_id: str) -> dict | None:
    """Load AI profile with decrypted API key."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, display_name, provider, api_key_ciphertext, style "
                "FROM ai_profiles WHERE id = %s AND active = true",
                (str(ai_id),),
            )
            return await cur.fetchone()


async def _transition_match(match_id: str, target_status: str, **kwargs) -> bool:
    """Transition match status in DB. Returns True on success."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT status FROM matches WHERE id = %s FOR UPDATE",
                (match_id,),
            )
            row = await cur.fetchone()
            if not row or not can_transition(row["status"], target_status):
                return False

            set_parts = ["status = %s"]
            params: list = [target_status]

            if target_status in ("completed", "forfeit", "aborted"):
                set_parts.append("completed_at = now()")

            if "winner_ai_id" in kwargs:
                set_parts.append("winner_ai_id = %s")
                params.append(kwargs["winner_ai_id"])

            if "forfeit_reason" in kwargs:
                set_parts.append("forfeit_reason = %s")
                params.append(kwargs["forfeit_reason"])

            if "pgn" in kwargs:
                set_parts.append("pgn = %s")
                params.append(kwargs["pgn"])

            params.append(match_id)
            await cur.execute(
                f"UPDATE matches SET {', '.join(set_parts)} WHERE id = %s",
                tuple(params),
            )
            await conn.commit()
            return True


async def _insert_move(
    match_id: str,
    ply: int,
    san: str,
    fen: str,
    eval_cp: int | None,
    think_summary: str,
    chat_line: str,
) -> None:
    """Insert a move into match_moves."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO match_moves "
                "(match_id, ply, san, fen, stockfish_eval_cp, think_summary, chat_line) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (match_id, ply, san, fen, eval_cp, think_summary, chat_line),
            )
            await conn.commit()


async def _update_elo(
    match_id: str,
    white_ai_id: str,
    black_ai_id: str,
    result: str,
) -> None:
    """Update ELO ratings transactionally. Per spec: single BEGIN...COMMIT block."""
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            # Get current ratings (INSERT default if missing)
            for ai_id in (white_ai_id, black_ai_id):
                await cur.execute(
                    "INSERT INTO elo_ratings (ai_id) VALUES (%s) "
                    "ON CONFLICT (ai_id) DO NOTHING",
                    (ai_id,),
                )

            await cur.execute(
                "SELECT ai_id, rating FROM elo_ratings "
                "WHERE ai_id = ANY(%s) FOR UPDATE",
                ([white_ai_id, black_ai_id],),
            )
            rows = await cur.fetchall()
            ratings = {str(r["ai_id"]): r["rating"] for r in rows}

            white_rating = ratings.get(white_ai_id, DEFAULT_RATING)
            black_rating = ratings.get(black_ai_id, DEFAULT_RATING)

            new_white, new_black = calculate_new_ratings(
                white_rating, black_rating, result,
            )

            # Update ratings and win/loss/draw counters
            if result == "white_win":
                w_col, b_col = "wins", "losses"
            elif result == "black_win":
                w_col, b_col = "losses", "wins"
            else:
                w_col, b_col = "draws", "draws"

            await cur.execute(
                f"UPDATE elo_ratings SET rating = %s, {w_col} = {w_col} + 1, "
                "updated_at = now() WHERE ai_id = %s",
                (new_white, white_ai_id),
            )
            await cur.execute(
                f"UPDATE elo_ratings SET rating = %s, {b_col} = {b_col} + 1, "
                "updated_at = now() WHERE ai_id = %s",
                (new_black, black_ai_id),
            )
            await conn.commit()

    logger.info(
        "ELO updated: white %s %d->%d, black %s %d->%d (%s)",
        white_ai_id, white_rating, new_white,
        black_ai_id, black_rating, new_black,
        result,
    )


def _board_to_pgn(board: chess.Board, white_name: str, black_name: str) -> str:
    """Generate PGN string from a completed board."""
    game = chess.pgn.Game.from_board(board)
    game.headers["White"] = white_name
    game.headers["Black"] = black_name
    game.headers["Event"] = "OmarBit Arena"
    result = board.result(claim_draw=True)
    game.headers["Result"] = result
    return str(game)


async def play_match(match_id: str) -> None:
    """Execute a full match from start to finish.

    This is the main entry point called by the Celery worker.
    """
    logger.info("Starting match %s", match_id)

    # Load match
    match = await _load_match(match_id)
    if not match:
        logger.error("Match %s not found", match_id)
        return

    if match["status"] != "scheduled":
        logger.warning("Match %s in state %s, expected scheduled", match_id, match["status"])
        return

    white_ai_id = str(match["white_ai_id"])
    black_ai_id = str(match["black_ai_id"])

    # Load AI profiles
    white_profile = await _load_ai_profile(white_ai_id)
    black_profile = await _load_ai_profile(black_ai_id)

    if not white_profile or not black_profile:
        logger.error("Missing AI profile for match %s", match_id)
        await _transition_match(
            match_id, "aborted",
            forfeit_reason="AI profile not found or inactive",
        )
        return

    # Decrypt API keys (decrypt only in handler scope; zero after use per spec)
    try:
        white_api_key = decrypt_api_key(bytes(white_profile["api_key_ciphertext"]))
        black_api_key = decrypt_api_key(bytes(black_profile["api_key_ciphertext"]))
    except Exception as exc:
        logger.error("Failed to decrypt API keys for match %s: %s", match_id, type(exc).__name__)
        await _transition_match(
            match_id, "aborted",
            forfeit_reason="API key decryption failed",
        )
        return

    # Transition to in_progress
    if not await _transition_match(match_id, "in_progress"):
        logger.error("Failed to transition match %s to in_progress", match_id)
        return

    await _publish_event(match_id, "match_start", {
        "match_id": match_id,
        "white_ai_id": white_ai_id,
        "black_ai_id": black_ai_id,
        "white_name": white_profile["display_name"],
        "black_name": black_profile["display_name"],
    })

    # Set up board and clock
    board = chess.Board()
    initial_time, increment = parse_time_control(match["time_control"])
    clock = MatchClock(
        white_time=initial_time,
        black_time=initial_time,
    )

    # Strike counters for moderation (per AI per match)
    strike_counts = {white_ai_id: 0, black_ai_id: 0}

    ply = 0
    try:
        while not board.is_game_over(claim_draw=True) and ply < MAX_PLIES:
            # Determine active player
            is_white_turn = board.turn == chess.WHITE
            active_ai_id = white_ai_id if is_white_turn else black_ai_id
            active_profile = white_profile if is_white_turn else black_profile
            active_api_key = white_api_key if is_white_turn else black_api_key

            # Check clock before requesting move
            clock.start_turn()
            if clock.is_flagged():
                winner = black_ai_id if is_white_turn else white_ai_id
                side = "White" if is_white_turn else "Black"
                logger.info("Match %s: %s flagged on time", match_id, side)
                await _transition_match(
                    match_id, "forfeit",
                    winner_ai_id=winner,
                    forfeit_reason=f"{side} flagged on time",
                    pgn=_board_to_pgn(board, white_profile["display_name"], black_profile["display_name"]),
                )
                result = "black_win" if is_white_turn else "white_win"
                await _update_elo(match_id, white_ai_id, black_ai_id, result)
                await _publish_event(match_id, "match_end", {
                    "status": "forfeit",
                    "winner_ai_id": winner,
                    "reason": f"{side} flagged on time",
                })
                return

            # Get legal moves
            legal_moves = [board.san(m) for m in board.legal_moves]

            # Build match context for the provider prompt
            match_context = {
                "match_id": match_id,
                "ply": ply,
                "white_name": white_profile["display_name"],
                "black_name": black_profile["display_name"],
                "is_white": is_white_turn,
                "white_time": clock.white_time,
                "black_time": clock.black_time,
            }

            # Request move from provider via orchestrator
            move_result = await orchestrate_move(
                provider_name=active_profile["provider"],
                api_key=active_api_key,
                fen=board.fen(),
                legal_moves=legal_moves,
                style=active_profile["style"],
                match_context=match_context,
                strike_count=strike_counts[active_ai_id],
            )

            if move_result.forfeit:
                winner = black_ai_id if is_white_turn else white_ai_id
                logger.info(
                    "Match %s: %s forfeited — %s",
                    match_id, active_profile["display_name"], move_result.forfeit_reason,
                )
                await _transition_match(
                    match_id, "forfeit",
                    winner_ai_id=winner,
                    forfeit_reason=move_result.forfeit_reason,
                    pgn=_board_to_pgn(board, white_profile["display_name"], black_profile["display_name"]),
                )
                result = "black_win" if is_white_turn else "white_win"
                await _update_elo(match_id, white_ai_id, black_ai_id, result)
                await _publish_event(match_id, "match_end", {
                    "status": "forfeit",
                    "winner_ai_id": winner,
                    "reason": move_result.forfeit_reason,
                })
                return

            # Apply move to board
            try:
                board.push_san(move_result.san)
            except (chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError) as exc:
                logger.error(
                    "Match %s: Invalid move %s from %s: %s",
                    match_id, move_result.san, active_profile["display_name"], exc,
                )
                winner = black_ai_id if is_white_turn else white_ai_id
                await _transition_match(
                    match_id, "forfeit",
                    winner_ai_id=winner,
                    forfeit_reason=f"Invalid move from {active_profile['display_name']}: {move_result.san}",
                    pgn=_board_to_pgn(board, white_profile["display_name"], black_profile["display_name"]),
                )
                result = "black_win" if is_white_turn else "white_win"
                await _update_elo(match_id, white_ai_id, black_ai_id, result)
                await _publish_event(match_id, "match_end", {
                    "status": "forfeit",
                    "winner_ai_id": winner,
                    "reason": f"Invalid move: {move_result.san}",
                })
                return

            # Record clock time consumed
            clock.end_turn()

            # Get Stockfish evaluation (non-blocking, best-effort)
            eval_cp = await evaluate_position(board.fen())

            # Track moderation strikes
            if move_result.chat_line == "[message filtered]":
                strike_counts[active_ai_id] += 1

            ply += 1

            # Persist move
            await _insert_move(
                match_id=match_id,
                ply=ply,
                san=move_result.san,
                fen=board.fen(),
                eval_cp=eval_cp,
                think_summary=move_result.think_summary,
                chat_line=move_result.chat_line,
            )

            # Publish move event
            await _publish_event(match_id, "move", {
                "ply": ply,
                "san": move_result.san,
                "fen": board.fen(),
                "eval_cp": eval_cp,
                "think_summary": move_result.think_summary,
                "chat_line": move_result.chat_line,
                "white_time": round(clock.white_time, 1),
                "black_time": round(clock.black_time, 1),
            })

            # Small delay to prevent overwhelming providers
            await asyncio.sleep(0.1)

        # Game over — determine result
        pgn_str = _board_to_pgn(board, white_profile["display_name"], black_profile["display_name"])

        if board.is_checkmate():
            # The side that just moved delivered checkmate
            winner = white_ai_id if board.turn == chess.BLACK else black_ai_id
            result = "white_win" if winner == white_ai_id else "black_win"
            await _transition_match(
                match_id, "completed",
                winner_ai_id=winner,
                pgn=pgn_str,
            )
        else:
            # Draw (stalemate, insufficient material, 50-move, repetition, max plies)
            result = "draw"
            await _transition_match(
                match_id, "completed",
                pgn=pgn_str,
            )

        await _update_elo(match_id, white_ai_id, black_ai_id, result)

        await _publish_event(match_id, "match_end", {
            "status": "completed",
            "result": result,
            "winner_ai_id": winner if result != "draw" else None,
            "pgn": pgn_str,
        })

        logger.info("Match %s completed: %s", match_id, result)

    except Exception as exc:
        logger.exception("Match %s crashed: %s", match_id, exc)
        await _transition_match(
            match_id, "aborted",
            forfeit_reason=f"Internal error: {type(exc).__name__}",
        )
        await _publish_event(match_id, "match_end", {
            "status": "aborted",
            "reason": "Internal error",
        })
    finally:
        # Zero API keys after use (spec anti-pattern guard)
        white_api_key = ""  # noqa: F841
        black_api_key = ""  # noqa: F841


# Alias for backward compatibility with the asyncio background task approach
run_match = play_match
