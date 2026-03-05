"""Gemini (Google) provider adapter."""

import json

from providers.base import BaseProvider, InvalidResponseError, MoveResponse
from providers.prompts import SYSTEM_PROMPT, build_user_prompt

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = "gemini-2.0-flash"


class GeminiProvider(BaseProvider):
    provider_name = "gemini"

    def _build_request(
        self,
        api_key: str,
        fen: str,
        legal_moves: list[str],
        style: str,
        match_context: dict,
    ) -> tuple[str, dict, dict]:
        user_prompt = build_user_prompt(fen, legal_moves, style, match_context)
        url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{SYSTEM_PROMPT}\n\n{user_prompt}"},
                    ],
                },
            ],
            "generationConfig": {
                "maxOutputTokens": 512,
                "responseMimeType": "application/json",
            },
        }
        return url, headers, body

    def _parse_response(self, data: dict) -> MoveResponse:
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            move = parsed["move"]
            think_summary = parsed.get("think_summary", "")[:500]
            chat_line = parsed.get("chat_line", "")[:280]
            return MoveResponse(san=move, think_summary=think_summary, chat_line=chat_line)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise InvalidResponseError(f"Gemini response parse error: {exc}") from exc
