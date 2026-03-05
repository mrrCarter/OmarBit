"""Tests for orchestrator commentary module."""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["SKIP_DB"] = "true"

import pytest

from orchestrator import (
    COMMENTARY_INTERVAL,
    generate_commentary,
    should_generate_commentary,
)


def test_should_generate_at_interval():
    assert should_generate_commentary(COMMENTARY_INTERVAL) is True
    assert should_generate_commentary(COMMENTARY_INTERVAL * 2) is True
    assert should_generate_commentary(COMMENTARY_INTERVAL * 3) is True


def test_should_not_generate_at_zero():
    assert should_generate_commentary(0) is False


def test_should_not_generate_between_intervals():
    assert should_generate_commentary(1) is False
    assert should_generate_commentary(COMMENTARY_INTERVAL - 1) is False
    assert should_generate_commentary(COMMENTARY_INTERVAL + 1) is False


@pytest.mark.asyncio
@patch("orchestrator.is_orchestrator_enabled", new_callable=AsyncMock, return_value=True)
@patch("orchestrator.httpx.AsyncClient")
async def test_generate_commentary_success(mock_client_cls, mock_enabled):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "commentary": "White is building a strong kingside attack.",
                        "phase": "middlegame",
                        "tension": "high",
                    })
                }
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        result = await generate_commentary(
            fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            recent_moves=["e4", "e5", "Nf3", "Nc6", "Bb5"],
            opening_name="Ruy Lopez",
            eval_cp=30,
            white_name="TestWhite",
            black_name="TestBlack",
            ply=5,
        )

    assert result is not None
    assert "kingside" in result["commentary"]
    assert result["phase"] == "middlegame"
    assert result["tension"] == "high"


@pytest.mark.asyncio
async def test_generate_commentary_no_api_key():
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
        result = await generate_commentary(
            fen="startpos",
            recent_moves=[],
            opening_name=None,
            eval_cp=None,
            white_name="W",
            black_name="B",
            ply=5,
        )
    assert result is None


@pytest.mark.asyncio
@patch("orchestrator.is_orchestrator_enabled", new_callable=AsyncMock, return_value=False)
async def test_generate_commentary_disabled(mock_enabled):
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        result = await generate_commentary(
            fen="startpos",
            recent_moves=[],
            opening_name=None,
            eval_cp=None,
            white_name="W",
            black_name="B",
            ply=5,
        )
    assert result is None


@pytest.mark.asyncio
@patch("orchestrator.is_orchestrator_enabled", new_callable=AsyncMock, return_value=True)
@patch("orchestrator.httpx.AsyncClient")
async def test_generate_commentary_api_error(mock_client_cls, mock_enabled):
    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        result = await generate_commentary(
            fen="startpos",
            recent_moves=[],
            opening_name=None,
            eval_cp=None,
            white_name="W",
            black_name="B",
            ply=5,
        )
    assert result is None


@pytest.mark.asyncio
@patch("orchestrator.is_orchestrator_enabled", new_callable=AsyncMock, return_value=True)
@patch("orchestrator.httpx.AsyncClient")
async def test_generate_commentary_truncates_long(mock_client_cls, mock_enabled):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "commentary": "x" * 600,
                        "phase": "endgame",
                        "tension": "low",
                    })
                }
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        result = await generate_commentary(
            fen="startpos",
            recent_moves=[],
            opening_name=None,
            eval_cp=None,
            white_name="W",
            black_name="B",
            ply=30,
        )

    assert result is not None
    assert len(result["commentary"]) <= 500
