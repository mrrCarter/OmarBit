"""Spectator commentary orchestrator — LLM-powered match narration.

Uses gpt-4o-mini to generate spectator-friendly commentary every N plies.
Feature-flagged via DB feature_flags table (key: orchestrator_enabled).

Detects game phases, references openings, and provides positional insights.
Publishes commentary SSE events and persists to match_commentary table.
"""

import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_COMMENTARY_MODEL = "gpt-4o-mini"
_COMMENTARY_TIMEOUT = 15.0
COMMENTARY_INTERVAL = 5  # Generate commentary every N plies

_COMMENTARY_PROMPT = (
    "You are a chess commentator for the OmarBit Arena, an AI-vs-AI chess platform. "
    "Your audience is chess enthusiasts (13+). Provide brief, engaging spectator commentary.\n\n"
    "You will receive:\n"
    "- Current FEN position\n"
    "- Recent moves (SAN notation)\n"
    "- Opening name (if detected)\n"
    "- Stockfish evaluation (centipawns, positive = white advantage)\n"
    "- Player names and game phase\n\n"
    "Respond with ONLY a JSON object:\n"
    '{"commentary": "1-2 sentence spectator insight", '
    '"phase": "opening|middlegame|endgame", '
    '"tension": "low|medium|high|critical"}\n\n'
    "Guidelines:\n"
    "- Reference famous games or patterns when relevant\n"
    "- Note tactical threats, positional imbalances, or critical moments\n"
    "- Keep it accessible — explain ideas, don't just list variations\n"
    "- Be energetic for sharp positions, measured for quiet ones"
)


async def is_orchestrator_enabled() -> bool:
    """Check if the orchestrator feature flag is enabled."""
    try:
        from db import get_conn

        async with get_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT enabled FROM feature_flags WHERE key = %s",
                    ("orchestrator_enabled",),
                )
                row = await cur.fetchone()
                return row["enabled"] if row else False  # Default: disabled
    except Exception:
        return False  # Fail closed — no commentary if we can't check


def should_generate_commentary(ply: int) -> bool:
    """Check if commentary should be generated at this ply."""
    return ply > 0 and ply % COMMENTARY_INTERVAL == 0


async def generate_commentary(
    fen: str,
    recent_moves: list[str],
    opening_name: str | None,
    eval_cp: int | None,
    white_name: str,
    black_name: str,
    ply: int,
) -> dict | None:
    """Generate spectator commentary for the current position.

    Returns dict with commentary, phase, tension — or None on failure.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    if not await is_orchestrator_enabled():
        return None

    # Determine approximate game phase from ply count
    if ply < 20:
        approx_phase = "opening"
    elif ply < 60:
        approx_phase = "middlegame"
    else:
        approx_phase = "endgame"

    # Build context for the LLM
    eval_desc = "equal"
    if eval_cp is not None:
        if eval_cp > 200:
            eval_desc = f"White is winning (+{eval_cp / 100:.1f})"
        elif eval_cp > 50:
            eval_desc = f"White has an edge (+{eval_cp / 100:.1f})"
        elif eval_cp < -200:
            eval_desc = f"Black is winning ({eval_cp / 100:.1f})"
        elif eval_cp < -50:
            eval_desc = f"Black has an edge ({eval_cp / 100:.1f})"

    user_content = (
        f"Position: {fen}\n"
        f"Recent moves: {', '.join(recent_moves[-10:])}\n"
        f"Opening: {opening_name or 'Unknown'}\n"
        f"Evaluation: {eval_desc}\n"
        f"Phase: {approx_phase} (ply {ply})\n"
        f"White: {white_name} | Black: {black_name}"
    )

    try:
        async with httpx.AsyncClient(timeout=_COMMENTARY_TIMEOUT) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _COMMENTARY_MODEL,
                    "messages": [
                        {"role": "system", "content": _COMMENTARY_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.7,
                },
            )

        if resp.status_code != 200:
            logger.warning("Commentary API error: %d", resp.status_code)
            return None

        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        result = json.loads(content)

        return {
            "commentary": result.get("commentary", "")[:500],
            "phase": result.get("phase", approx_phase),
            "tension": result.get("tension", "medium"),
        }

    except (httpx.TimeoutException, httpx.ConnectError):
        logger.warning("Commentary timeout/connection error")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("Commentary parse error: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Commentary unexpected error: %s", exc)
        return None


async def persist_commentary(
    match_id: str,
    ply_start: int,
    ply_end: int,
    commentary: str,
    opening_name: str | None,
    game_phase: str | None,
) -> None:
    """Store commentary in the database."""
    try:
        from db import get_conn

        async with get_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO match_commentary "
                    "(match_id, ply_start, ply_end, commentary, opening_name, game_phase) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (match_id, ply_start, ply_end, commentary, opening_name, game_phase),
                )
                await conn.commit()
    except Exception as exc:
        logger.warning("Failed to persist commentary: %s", exc)
