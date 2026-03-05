"""Tests for provider prompt templates — thought-stream contract compliance."""

from providers.prompts import STYLE_INSTRUCTIONS, SYSTEM_PROMPT, build_user_prompt


def test_system_prompt_requests_json():
    assert "JSON" in SYSTEM_PROMPT


def test_system_prompt_forbids_cot():
    assert "chain-of-thought" in SYSTEM_PROMPT.lower()


def test_system_prompt_enforces_teen_safe():
    assert "13+" in SYSTEM_PROMPT


def test_all_styles_have_instructions():
    for style in ("aggressive", "positional", "balanced", "chaotic", "defensive"):
        assert style in STYLE_INSTRUCTIONS


def test_build_user_prompt_white():
    prompt = build_user_prompt(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        ["e4", "d4"],
        "aggressive",
        {"ply": 0},
    )
    assert "White" in prompt
    assert "e4" in prompt
    assert "d4" in prompt
    assert "FEN" in prompt


def test_build_user_prompt_black():
    prompt = build_user_prompt(
        "some-fen",
        ["e5"],
        "defensive",
        {"ply": 1},
    )
    assert "Black" in prompt


def test_build_user_prompt_move_number():
    prompt = build_user_prompt("fen", ["e4"], "balanced", {"ply": 4})
    assert "Move number: 3" in prompt


def test_build_user_prompt_unknown_style_defaults_balanced():
    prompt = build_user_prompt("fen", ["e4"], "unknown_style", {"ply": 0})
    assert "balanced" in prompt.lower()
