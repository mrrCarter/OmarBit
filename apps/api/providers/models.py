"""Model registry — available models per provider with cost info."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelInfo:
    id: str
    name: str
    provider: str
    cost_per_1m_input: float   # USD per 1M input tokens
    cost_per_1m_output: float  # USD per 1M output tokens


# All available models per provider
MODELS: dict[str, list[ModelInfo]] = {
    "claude": [
        ModelInfo("claude-sonnet-4-20250514", "Claude Sonnet 4", "claude", 3.00, 15.00),
        ModelInfo("claude-sonnet-4-6", "Claude Sonnet 4.6", "claude", 3.00, 15.00),
        ModelInfo("claude-haiku-4-5-20251001", "Claude Haiku 4.5", "claude", 0.80, 4.00),
        ModelInfo("claude-opus-4-6", "Claude Opus 4.6", "claude", 15.00, 75.00),
        ModelInfo("claude-opus-4-5", "Claude Opus 4.5", "claude", 15.00, 75.00),
        ModelInfo("claude-opus-4-1", "Claude Opus 4.1", "claude", 15.00, 75.00),
    ],
    "gpt": [
        ModelInfo("gpt-4o", "GPT-4o", "gpt", 2.50, 10.00),
        ModelInfo("gpt-4o-mini", "GPT-4o Mini", "gpt", 0.15, 0.60),
        ModelInfo("gpt-4.1", "GPT-4.1", "gpt", 2.00, 8.00),
        ModelInfo("gpt-4.1-mini", "GPT-4.1 Mini", "gpt", 0.40, 1.60),
        ModelInfo("gpt-4.1-nano", "GPT-4.1 Nano", "gpt", 0.10, 0.40),
        ModelInfo("gpt-5", "GPT-5", "gpt", 2.00, 8.00),
        ModelInfo("gpt-5-mini", "GPT-5 Mini", "gpt", 0.40, 1.60),
        ModelInfo("gpt-5-nano", "GPT-5 Nano", "gpt", 0.10, 0.40),
        ModelInfo("codex-5.3", "Codex 5.3", "gpt", 2.00, 8.00),
        ModelInfo("codex-5", "Codex 5", "gpt", 2.00, 8.00),
    ],
    "grok": [
        ModelInfo("grok-3", "Grok 3", "grok", 3.00, 15.00),
        ModelInfo("grok-3-fast", "Grok 3 Fast", "grok", 1.50, 7.50),
        ModelInfo("grok-3-mini", "Grok 3 Mini", "grok", 0.30, 0.50),
        ModelInfo("grok-2", "Grok 2", "grok", 2.00, 10.00),
    ],
    "gemini": [
        ModelInfo("gemini-2.5-flash", "Gemini 2.5 Flash", "gemini", 0.15, 0.60),
        ModelInfo("gemini-2.0-flash", "Gemini 2.0 Flash", "gemini", 0.10, 0.40),
        ModelInfo("gemini-3.1-pro", "Gemini 3.1 Pro", "gemini", 2.00, 10.00),
        ModelInfo("gemini-3.1-flash", "Gemini 3.1 Flash", "gemini", 0.20, 0.80),
        ModelInfo("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", "gemini", 0.10, 0.40),
        ModelInfo("gemini-3.0-pro", "Gemini 3.0 Pro", "gemini", 1.50, 8.00),
        ModelInfo("gemini-3.0-flash", "Gemini 3.0 Flash", "gemini", 0.15, 0.60),
        ModelInfo("gemini-3.0-flash-lite", "Gemini 3.0 Flash Lite", "gemini", 0.10, 0.40),
    ],
}

# Flat lookup: model_id -> ModelInfo
_MODEL_INDEX: dict[str, ModelInfo] = {}
for _models in MODELS.values():
    for _m in _models:
        _MODEL_INDEX[_m.id] = _m


def get_model_info(model_id: str) -> ModelInfo | None:
    """Get model info by ID. Returns None for unknown models."""
    return _MODEL_INDEX.get(model_id)


def get_models_for_provider(provider: str) -> list[ModelInfo]:
    """Get all available models for a provider."""
    return MODELS.get(provider, [])


def get_default_model(provider: str) -> str:
    """Get the default model ID for a provider."""
    models = MODELS.get(provider)
    if models:
        return models[0].id
    return ""


def is_valid_model(provider: str, model_id: str) -> bool:
    """Check if a model ID is valid for the given provider."""
    models = MODELS.get(provider, [])
    return any(m.id == model_id for m in models)
