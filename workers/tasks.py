"""Celery tasks for match orchestration."""

import asyncio
import logging

from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(name="workers.play_match", bind=True, max_retries=0)
def play_match_task(self, match_id: str) -> dict:
    """Execute a match as a Celery task.

    Wraps the async game loop in asyncio.run() for Celery compatibility.
    """
    from game_loop import play_match

    logger.info("Celery task starting match %s", match_id)
    try:
        asyncio.run(play_match(match_id))
        return {"match_id": match_id, "status": "completed"}
    except Exception as exc:
        logger.exception("Celery task failed for match %s: %s", match_id, exc)
        return {"match_id": match_id, "status": "error", "error": str(exc)}
