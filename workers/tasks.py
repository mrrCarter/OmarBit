"""Celery tasks for match orchestration."""

import asyncio
import logging

from workers.celery_app import app

logger = logging.getLogger(__name__)


async def _run_match(match_id: str) -> None:
    """Initialize DB pool, run the game loop, then tear down."""
    from db import close_pool, init_pool
    from game_loop import play_match

    await init_pool()
    try:
        await play_match(match_id)
    finally:
        await close_pool()


@app.task(name="workers.play_match", bind=True, max_retries=0)
def play_match_task(self, match_id: str) -> dict:
    """Execute a match as a Celery task.

    Wraps the async game loop in asyncio.run() for Celery compatibility.
    """
    logger.info("Celery task starting match %s", match_id)
    try:
        asyncio.run(_run_match(match_id))
        return {"match_id": match_id, "status": "completed"}
    except Exception as exc:
        logger.exception("Celery task failed for match %s: %s", match_id, exc)
        return {"match_id": match_id, "status": "error", "error": str(exc)}
