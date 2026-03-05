import os

import httpx

STOCKFISH_URL = os.environ.get("STOCKFISH_URL", "http://localhost:8080")

# Timeout/retry values from spec Section 7
_CONNECT_TIMEOUT = 1.0
_READ_TIMEOUT = 5.0
_MAX_RETRIES = 1
_BACKOFF = 0.2


async def validate_move(fen: str, san: str) -> bool:
    """Validate a chess move via the Stockfish service.

    Returns True if the move is legal, False otherwise.
    Raises RuntimeError on unrecoverable service errors.
    """
    attempt = 0
    last_err: Exception | None = None
    while attempt <= _MAX_RETRIES:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT),
            ) as client:
                resp = await client.post(
                    f"{STOCKFISH_URL}/validate",
                    json={"fen": fen, "move": san},
                    timeout=httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return bool(data.get("legal", False))
                if resp.status_code == 400:
                    return False
                resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.HTTPStatusError) as exc:
            last_err = exc
            attempt += 1
            if attempt <= _MAX_RETRIES:
                import asyncio
                await asyncio.sleep(_BACKOFF)
    raise RuntimeError(f"Stockfish service unavailable after {_MAX_RETRIES + 1} attempts: {last_err}")


async def evaluate_position(fen: str) -> int | None:
    """Get Stockfish evaluation in centipawns. Returns None on failure."""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT),
        ) as client:
            resp = await client.post(
                f"{STOCKFISH_URL}/evaluate",
                json={"fen": fen},
                timeout=httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT),
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("eval_cp")
    except (httpx.ConnectError, httpx.ReadTimeout):
        pass
    return None
