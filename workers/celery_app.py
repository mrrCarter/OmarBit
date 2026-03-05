"""Celery application configuration for OmarBit match workers."""

import os
import sys
from pathlib import Path

# Load .env.local from repo root so workers pick up DB/Redis/encryption config
from dotenv import load_dotenv

_repo_root = Path(__file__).resolve().parent.parent
load_dotenv(_repo_root / ".env.local")

# Add apps/api to Python path so workers can import game_loop, db, etc.
_api_dir = str(_repo_root / "apps" / "api")
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from celery import Celery  # noqa: E402

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380/0")

app = Celery(
    "omarbit",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
    task_time_limit=1800,
    task_soft_time_limit=1500,
)

app.autodiscover_tasks(["workers"])
