import datetime
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env.local")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from db import DatabaseUnavailableError, close_pool, init_pool
from routers.ai_profiles import router as ai_profiles_router
from routers.feature_flags import router as feature_flags_router
from routers.leaderboard import router as leaderboard_router
from routers.matches import router as matches_router
from routers.replay import router as replay_router
from routers.sse import router as sse_router
from routers.tournaments import router as tournaments_router

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

SKIP_DB = os.getenv("SKIP_DB", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not SKIP_DB:
        await init_pool()
    yield
    if not SKIP_DB:
        await close_pool()


app = FastAPI(title="OmarBit API", version="0.1.0", lifespan=lifespan)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client_id = ""
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                client_id = value.decode("latin-1")
                break

        request_id = client_id if _UUID_RE.match(client_id) else str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["x-request-id"] = request_id
            await send(message)

        await self.app(scope, receive, send_with_request_id)


app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DatabaseUnavailableError)
async def db_unavailable_handler(request: Request, exc: DatabaseUnavailableError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": str(exc),
            },
            "requestId": request_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Unexpected error",
            },
            "requestId": request_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    )


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(feature_flags_router)
app.include_router(ai_profiles_router)
app.include_router(matches_router)
app.include_router(sse_router)
app.include_router(leaderboard_router)
app.include_router(replay_router)
app.include_router(tournaments_router)
