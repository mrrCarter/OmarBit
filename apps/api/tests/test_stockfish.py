import pytest

from stockfish import _BACKOFF, _CONNECT_TIMEOUT, _MAX_RETRIES, _READ_TIMEOUT


def test_timeout_values_match_spec():
    """Verify timeout/retry values match the spec table (Section 7)."""
    assert _CONNECT_TIMEOUT == 1.0
    assert _READ_TIMEOUT == 5.0
    assert _MAX_RETRIES == 1
    assert _BACKOFF == 0.2


@pytest.mark.asyncio
async def test_validate_move_raises_on_unavailable_service():
    """Stockfish service is not running in CI — should raise RuntimeError."""
    from stockfish import validate_move
    with pytest.raises(RuntimeError, match="Stockfish service unavailable"):
        await validate_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e4")
