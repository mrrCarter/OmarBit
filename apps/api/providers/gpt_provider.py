"""GPT (OpenAI) provider adapter."""

import json

from providers.base import BaseProvider, InvalidResponseError, MoveResponse
from providers.prompts import SYSTEM_PROMPT, build_user_prompt

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o"


class GPTProvider(BaseProvider):
    provider_name = "gpt"

    def _build_request(
        self,
        api_key: str,
        fen: str,
        legal_moves: list[str],
        style: str,
        match_context: dict,
    ) -> tuple[str, dict, dict]:
        user_prompt = build_user_prompt(fen, legal_moves, style, match_context)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": OPENAI_MODEL,
            "max_tokens": 512,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        return OPENAI_API_URL, headers, body

    def _parse_response(self, data: dict) -> MoveResponse:
        try:
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            move = parsed["move"]
            think_summary = parsed.get("think_summary", "")[:500]
            chat_line = parsed.get("chat_line", "")[:280]
            return MoveResponse(san=move, think_summary=think_summary, chat_line=chat_line)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise InvalidResponseError(f"GPT response parse error: {exc}") from exc
