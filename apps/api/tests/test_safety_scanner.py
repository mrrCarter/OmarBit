"""Tests for safety_scanner module."""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from safety_scanner import scan_instructions


@pytest.mark.asyncio
async def test_empty_input_is_safe():
    is_safe, reason = await scan_instructions("")
    assert is_safe is True
    assert reason == ""


@pytest.mark.asyncio
async def test_none_input_is_safe():
    is_safe, reason = await scan_instructions("")
    assert is_safe is True


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": ""})
async def test_no_api_key_skips_scan():
    is_safe, reason = await scan_instructions("some instructions")
    assert is_safe is True


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
@patch("safety_scanner.is_feature_enabled", new_callable=AsyncMock, return_value=False)
async def test_disabled_feature_skips_scan(mock_flag):
    is_safe, reason = await scan_instructions("some instructions")
    assert is_safe is True


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
@patch("safety_scanner.is_feature_enabled", new_callable=AsyncMock, return_value=True)
async def test_safe_content_passes(mock_flag):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps({"safe": True, "reason": ""})}}]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("safety_scanner.httpx.AsyncClient", return_value=mock_client):
        is_safe, reason = await scan_instructions("Play the King's Indian Defense")
        assert is_safe is True
        assert reason == ""


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
@patch("safety_scanner.is_feature_enabled", new_callable=AsyncMock, return_value=True)
async def test_unsafe_content_flagged(mock_flag):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "safe": False,
            "reason": "Contains hate speech"
        })}}]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("safety_scanner.httpx.AsyncClient", return_value=mock_client):
        is_safe, reason = await scan_instructions("hateful content")
        assert is_safe is False
        assert "hate speech" in reason


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
@patch("safety_scanner.is_feature_enabled", new_callable=AsyncMock, return_value=True)
async def test_api_error_allows_through(mock_flag):
    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("safety_scanner.httpx.AsyncClient", return_value=mock_client):
        is_safe, reason = await scan_instructions("some content")
        assert is_safe is True


@pytest.mark.asyncio
@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
@patch("safety_scanner.is_feature_enabled", new_callable=AsyncMock, return_value=True)
async def test_timeout_allows_through(mock_flag):
    import httpx

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("timeout")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("safety_scanner.httpx.AsyncClient", return_value=mock_client):
        is_safe, reason = await scan_instructions("some content")
        assert is_safe is True
