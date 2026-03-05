"""Provider registry — maps provider name to adapter instance."""

from providers.base import BaseProvider
from providers.claude_provider import ClaudeProvider
from providers.gemini_provider import GeminiProvider
from providers.gpt_provider import GPTProvider
from providers.grok_provider import GrokProvider

_PROVIDERS: dict[str, BaseProvider] = {
    "claude": ClaudeProvider(),
    "gpt": GPTProvider(),
    "grok": GrokProvider(),
    "gemini": GeminiProvider(),
}


def get_provider(name: str) -> BaseProvider:
    """Get provider adapter by name. Raises ValueError for unknown providers."""
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"Unknown provider: {name!r}. Valid: {list(_PROVIDERS.keys())}")
    return provider
