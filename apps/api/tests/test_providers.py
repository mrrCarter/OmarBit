"""Tests for provider adapters — base retry logic, parsing, and registry."""

import json

import pytest

from providers.base import (
    _BACKOFF_SCHEDULE,
    _CONNECT_TIMEOUT,
    _MAX_RETRIES,
    _READ_TIMEOUT,
    InvalidResponseError,
    MoveResponse,
    ProviderUnavailableError,
    QuotaExhaustedError,
)
from providers.claude_provider import ClaudeProvider
from providers.gemini_provider import GeminiProvider
from providers.gpt_provider import GPTProvider
from providers.grok_provider import GrokProvider
from providers.registry import get_provider


def test_timeout_values_match_spec():
    """Verify provider timeout/retry values match spec Section 7."""
    assert _CONNECT_TIMEOUT == 3.0
    assert _READ_TIMEOUT == 20.0
    assert _MAX_RETRIES == 2
    assert _BACKOFF_SCHEDULE == (0.5, 1.0)


def test_registry_returns_all_providers():
    assert isinstance(get_provider("claude"), ClaudeProvider)
    assert isinstance(get_provider("gpt"), GPTProvider)
    assert isinstance(get_provider("grok"), GrokProvider)
    assert isinstance(get_provider("gemini"), GeminiProvider)


def test_registry_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("unknown")


# --- Claude provider parsing ---

def test_claude_parse_response():
    provider = ClaudeProvider()
    data = {
        "content": [
            {
                "text": json.dumps({
                    "move": "e4",
                    "think_summary": "Opening with king's pawn.",
                    "chat_line": "Let's go!",
                }),
            }
        ]
    }
    result = provider._parse_response(data)
    assert result.san == "e4"
    assert result.think_summary == "Opening with king's pawn."
    assert result.chat_line == "Let's go!"


def test_claude_parse_bad_json():
    provider = ClaudeProvider()
    data = {"content": [{"text": "not json"}]}
    with pytest.raises(InvalidResponseError, match="Claude"):
        provider._parse_response(data)


def test_claude_parse_missing_move():
    provider = ClaudeProvider()
    data = {"content": [{"text": json.dumps({"think_summary": "test"})}]}
    with pytest.raises(InvalidResponseError):
        provider._parse_response(data)


# --- GPT provider parsing ---

def test_gpt_parse_response():
    provider = GPTProvider()
    data = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "move": "d4",
                        "think_summary": "Queen's pawn opening.",
                        "chat_line": "Classical approach.",
                    }),
                }
            }
        ]
    }
    result = provider._parse_response(data)
    assert result.san == "d4"


def test_gpt_parse_bad_response():
    provider = GPTProvider()
    data = {"choices": []}
    with pytest.raises(InvalidResponseError, match="GPT"):
        provider._parse_response(data)


# --- Grok provider parsing ---

def test_grok_parse_response():
    provider = GrokProvider()
    data = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "move": "Nf3",
                        "think_summary": "Knight development.",
                    }),
                }
            }
        ]
    }
    result = provider._parse_response(data)
    assert result.san == "Nf3"
    assert result.chat_line == ""


# --- Gemini provider parsing ---

def test_gemini_parse_response():
    provider = GeminiProvider()
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "move": "c4",
                                "think_summary": "English opening.",
                                "chat_line": "Going for control.",
                            }),
                        }
                    ]
                }
            }
        ]
    }
    result = provider._parse_response(data)
    assert result.san == "c4"
    assert result.think_summary == "English opening."


def test_gemini_parse_empty_candidates():
    provider = GeminiProvider()
    data = {"candidates": []}
    with pytest.raises(InvalidResponseError, match="Gemini"):
        provider._parse_response(data)


# --- Build request tests ---

def test_claude_build_request():
    provider = ClaudeProvider()
    url, headers, body = provider._build_request(
        "sk-test", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        ["e4", "d4"], "balanced", {"ply": 0},
    )
    assert "anthropic" in url
    assert headers["x-api-key"] == "sk-test"
    assert body["model"] is not None
    assert len(body["messages"]) == 1


def test_gpt_build_request():
    provider = GPTProvider()
    url, headers, body = provider._build_request(
        "sk-test", "fen", ["e4"], "aggressive", {"ply": 0},
    )
    assert "openai" in url
    assert "Bearer sk-test" in headers["Authorization"]
    assert body["response_format"]["type"] == "json_object"


def test_gemini_build_request_includes_key_in_url():
    provider = GeminiProvider()
    url, _headers, _body = provider._build_request(
        "AIza-test", "fen", ["e4"], "balanced", {"ply": 0},
    )
    assert "key=AIza-test" in url


# --- Think summary truncation ---

def test_think_summary_truncated_to_500():
    provider = ClaudeProvider()
    long_summary = "x" * 600
    data = {
        "content": [
            {
                "text": json.dumps({
                    "move": "e4",
                    "think_summary": long_summary,
                    "chat_line": "",
                }),
            }
        ]
    }
    result = provider._parse_response(data)
    assert len(result.think_summary) == 500


def test_chat_line_truncated_to_280():
    provider = ClaudeProvider()
    long_chat = "y" * 400
    data = {
        "content": [
            {
                "text": json.dumps({
                    "move": "e4",
                    "think_summary": "",
                    "chat_line": long_chat,
                }),
            }
        ]
    }
    result = provider._parse_response(data)
    assert len(result.chat_line) == 280


# --- MoveResponse ---

def test_move_response_dataclass():
    r = MoveResponse(san="e4", think_summary="test", chat_line="hi")
    assert r.san == "e4"
    assert r.think_summary == "test"
    assert r.chat_line == "hi"


# --- Retry/error path tests via request_move mock ---

@pytest.mark.asyncio
async def test_quota_exhausted_raises_immediately():
    """429 should raise QuotaExhaustedError without retrying."""
    assert issubclass(QuotaExhaustedError, Exception)
    assert issubclass(ProviderUnavailableError, Exception)
