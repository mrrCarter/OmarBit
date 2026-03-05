"""Claude (Anthropic) provider adapter."""

import json

from providers.base import BaseProvider, InvalidResponseError, MoveResponse
from providers.prompts import SYSTEM_PROMPT, build_user_prompt

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ClaudeProvider(BaseProvider):
    provider_name = "claude"

    def _build_request(
        self,
        api_key: str,
        fen: str,
        legal_moves: list[str],
        style: str,
        match_context: dict,
    ) -> tuple[str, dict, dict]:
        user_prompt = build_user_prompt(fen, legal_moves, style, match_context)
        model = match_context.get("model") or ANTHROPIC_DEFAULT_MODEL
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": 256,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        return ANTHROPIC_API_URL, headers, body

    def _parse_response(self, data: dict) -> MoveResponse:
        try:
            content = data["content"][0]["text"]
            parsed = json.loads(content)
            move = parsed["move"]
            think_summary = parsed.get("think_summary", "")[:500]
            chat_line = parsed.get("chat_line", "")[:280]
            return MoveResponse(san=move, think_summary=think_summary, chat_line=chat_line)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise InvalidResponseError(f"Claude response parse error: {exc}") from exc
