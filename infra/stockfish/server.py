"""Minimal Stockfish HTTP wrapper exposing /validate, /evaluate, and /health."""

import chess
import chess.engine
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager

engine: chess.engine.UciProtocol | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    _, engine = await chess.engine.popen_uci("/usr/games/stockfish")
    yield
    if engine:
        await engine.quit()


app = FastAPI(lifespan=lifespan)


class ValidateRequest(BaseModel):
    fen: str
    move: str


class EvaluateRequest(BaseModel):
    fen: str


@app.get("/health")
async def health():
    if engine is None:
        raise HTTPException(status_code=503, detail="engine not ready")
    return {"status": "ok"}


@app.post("/validate")
async def validate(req: ValidateRequest):
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid FEN")
    try:
        move = board.parse_san(req.move)
        legal = move in board.legal_moves
    except (chess.InvalidMoveError, chess.IllegalMoveError, ValueError):
        legal = False
    return {"legal": legal}


@app.post("/evaluate")
async def evaluate(req: EvaluateRequest):
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid FEN")
    if engine is None:
        raise HTTPException(status_code=503, detail="engine not ready")
    info = await engine.analyse(board, chess.engine.Limit(depth=18))
    score = info.get("score")
    if score is None:
        return {"eval_cp": None}
    cp = score.white().score(mate_score=10000)
    return {"eval_cp": cp}
