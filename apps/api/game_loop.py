"""Async game loop — runs a match from scheduled to completion.

Spawned as a background asyncio task when a match is created.
Handles the full lifecycle: transition states, orchestrate moves,
persist results, update ELO.
"""

import asyncio
import logging

import chess

from db import get_conn
from elo import DEFAULT_RATING, calculate_new_ratings
from encryption import decrypt_api_key
from move_orchestrator import orchestrate_move
from stockfish import evaluate_position

logger = logging.getLogger(__name__)

# Max plies before declaring a draw (prevents infinite games)
MAX_PLIES = 300


async def run_match(match_id: str) -> None:
    """Run a full match to completion."""
    # Small delay to let the DB transaction commit
    await asyncio.sleep(0.5)

    try:
        await _run_match_inner(match_id)
    except Exception:
        logger.exception("Game loop crashed for match %s", match_id)
        try:
            async with get_conn() as conn:
                await conn.execute(
                    "UPDATE matches SET status = 'aborted', "
                    "forfeit_reason = 'Internal game loop error', "
                    "completed_at = now() WHERE id = %s AND status IN ('scheduled', 'in_progress')",
                    (match_id,),
                )
                await conn.commit()
        except Exception:
            logger.exception("Failed to abort match %s after crash", match_id)


async def _run_match_inner(match_id: str) -> None:
    # Load match and AI profiles
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT m.id, m.white_ai_id, m.black_ai_id, m.status, "
                "w.provider AS w_provider, w.api_key_ciphertext AS w_key, w.style AS w_style, w.display_name AS w_name, "
                "b.provider AS b_provider, b.api_key_ciphertext AS b_key, b.style AS b_style, b.display_name AS b_name "
                "FROM matches m "
                "JOIN ai_profiles w ON w.id = m.white_ai_id "
                "JOIN ai_profiles b ON b.id = m.black_ai_id "
                "WHERE m.id = %s",
                (match_id,),
            )
            row = await cur.fetchone()

    if not row:
        logger.error("Match %s not found", match_id)
        return

    if row["status"] != "scheduled":
        logger.warning("Match %s not in scheduled state (is %s)", match_id, row["status"])
        return

    # Decrypt API keys
    white_key = decrypt_api_key(bytes(row["w_key"]))
    black_key = decrypt_api_key(bytes(row["b_key"]))

    white = {
        "ai_id": str(row["white_ai_id"]),
        "provider": row["w_provider"],
        "api_key": white_key,
        "style": row["w_style"],
        "name": row["w_name"],
    }
    black = {
        "ai_id": str(row["black_ai_id"]),
        "provider": row["b_provider"],
        "api_key": black_key,
        "style": row["b_style"],
        "name": row["b_name"],
    }

    # Transition to in_progress
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE matches SET status = 'in_progress' WHERE id = %s AND status = 'scheduled'",
            (match_id,),
        )
        await conn.commit()

    board = chess.Board()
    ply = 0
    strike_counts = {"white": 0, "black": 0}

    while not board.is_game_over() and ply < MAX_PLIES:
        side = white if board.turn == chess.WHITE else black
        side_name = "white" if board.turn == chess.WHITE else "black"

        legal_moves = [board.san(m) for m in board.legal_moves]
        fen = board.fen()

        result = await orchestrate_move(
            provider_name=side["provider"],
            api_key=side["api_key"],
            fen=fen,
            legal_moves=legal_moves,
            style=side["style"],
            match_context={"ply": ply, "side": side_name},
            strike_count=strike_counts[side_name],
        )

        if result.forfeit:
            # The moving side forfeits — opponent wins
            winner_id = black["ai_id"] if side_name == "white" else white["ai_id"]
            async with get_conn() as conn:
                await conn.execute(
                    "UPDATE matches SET status = 'forfeit', winner_ai_id = %s, "
                    "forfeit_reason = %s, completed_at = now() WHERE id = %s",
                    (winner_id, result.forfeit_reason, match_id),
                )
                await conn.commit()
            await _update_elo(match_id, white["ai_id"], black["ai_id"],
                              "black_win" if side_name == "white" else "white_win")
            logger.info("Match %s: %s forfeited — %s", match_id, side["name"], result.forfeit_reason)
            return

        # Apply move to board
        move = board.parse_san(result.san)
        board.push(move)
        new_fen = board.fen()

        # Get Stockfish eval (non-blocking, best-effort)
        eval_cp = await evaluate_position(new_fen)

        # Persist the move
        async with get_conn() as conn:
            await conn.execute(
                "INSERT INTO match_moves (match_id, ply, san, fen, stockfish_eval_cp, think_summary, chat_line) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (match_id, ply, result.san, new_fen, eval_cp, result.think_summary, result.chat_line),
            )
            await conn.commit()

        logger.info("Match %s ply %d: %s played %s", match_id, ply, side["name"], result.san)
        ply += 1

        # Small delay between moves so SSE clients can keep up
        await asyncio.sleep(0.3)

    # Game over — determine result
    if board.is_checkmate():
        # The side whose turn it is has been checkmated
        if board.turn == chess.WHITE:
            match_result = "black_win"
            winner_id = black["ai_id"]
        else:
            match_result = "white_win"
            winner_id = white["ai_id"]
    else:
        # Draw (stalemate, 50-move, insufficient material, repetition, or max plies)
        match_result = "draw"
        winner_id = None

    # Build PGN
    pgn_str = _build_pgn(board, white["name"], black["name"], match_result)

    async with get_conn() as conn:
        await conn.execute(
            "UPDATE matches SET status = 'completed', winner_ai_id = %s, "
            "pgn = %s, completed_at = now() WHERE id = %s",
            (winner_id, pgn_str, match_id),
        )
        await conn.commit()

    await _update_elo(match_id, white["ai_id"], black["ai_id"], match_result)
    logger.info("Match %s completed: %s", match_id, match_result)


async def _update_elo(match_id: str, white_ai_id: str, black_ai_id: str, result: str) -> None:
    """Update ELO ratings for both AIs."""
    try:
        async with get_conn() as conn:
            async with conn.cursor() as cur:
                # Get or create ratings
                for ai_id in (white_ai_id, black_ai_id):
                    await cur.execute(
                        "INSERT INTO elo_ratings (ai_id, rating, wins, losses, draws) "
                        "VALUES (%s, %s, 0, 0, 0) ON CONFLICT (ai_id) DO NOTHING",
                        (ai_id, DEFAULT_RATING),
                    )

                await cur.execute(
                    "SELECT ai_id, rating FROM elo_ratings WHERE ai_id = ANY(%s)",
                    ([white_ai_id, black_ai_id],),
                )
                rows = await cur.fetchall()
                ratings = {str(r["ai_id"]): r["rating"] for r in rows}

                w_rating = ratings.get(white_ai_id, DEFAULT_RATING)
                b_rating = ratings.get(black_ai_id, DEFAULT_RATING)
                new_w, new_b = calculate_new_ratings(w_rating, b_rating, result)

                # Update white
                w_wins = 1 if result == "white_win" else 0
                w_losses = 1 if result == "black_win" else 0
                w_draws = 1 if result == "draw" else 0
                await cur.execute(
                    "UPDATE elo_ratings SET rating = %s, wins = wins + %s, "
                    "losses = losses + %s, draws = draws + %s, updated_at = now() "
                    "WHERE ai_id = %s",
                    (new_w, w_wins, w_losses, w_draws, white_ai_id),
                )

                # Update black
                b_wins = 1 if result == "black_win" else 0
                b_losses = 1 if result == "white_win" else 0
                b_draws = 1 if result == "draw" else 0
                await cur.execute(
                    "UPDATE elo_ratings SET rating = %s, wins = wins + %s, "
                    "losses = losses + %s, draws = draws + %s, updated_at = now() "
                    "WHERE ai_id = %s",
                    (new_b, b_wins, b_losses, b_draws, black_ai_id),
                )

                await conn.commit()
    except Exception:
        logger.exception("Failed to update ELO for match %s", match_id)


def _build_pgn(board: chess.Board, white_name: str, black_name: str, result: str) -> str:
    """Build a minimal PGN string from the board's move stack."""
    import chess.pgn
    import io

    game = chess.pgn.Game()
    game.headers["White"] = white_name
    game.headers["Black"] = black_name
    if result == "white_win":
        game.headers["Result"] = "1-0"
    elif result == "black_win":
        game.headers["Result"] = "0-1"
    else:
        game.headers["Result"] = "1/2-1/2"

    node = game
    temp = chess.Board()
    for move in board.move_stack:
        node = node.add_variation(move)
        temp.push(move)

    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
    return game.accept(exporter)
