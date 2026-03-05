import datetime
import os
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import close_pool, init_pool
from routers.ai_profiles import router as ai_profiles_router
from routers.feature_flags import router as feature_flags_router
from routers.leaderboard import router as leaderboard_router
from routers.matches import router as matches_router
from routers.replay import router as replay_router
from routers.sse import router as sse_router

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    client_id = request.headers.get("x-request-id", "")
    request_id = client_id if _UUID_RE.match(client_id) else str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


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
