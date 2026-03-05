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
    ],
    "gpt": [
        ModelInfo("gpt-4o", "GPT-4o", "gpt", 2.50, 10.00),
        ModelInfo("gpt-4o-mini", "GPT-4o Mini", "gpt", 0.15, 0.60),
        ModelInfo("gpt-4.1", "GPT-4.1", "gpt", 2.00, 8.00),
        ModelInfo("gpt-4.1-mini", "GPT-4.1 Mini", "gpt", 0.40, 1.60),
        ModelInfo("gpt-4.1-nano", "GPT-4.1 Nano", "gpt", 0.10, 0.40),
    ],
    "grok": [
        ModelInfo("grok-3", "Grok 3", "grok", 3.00, 15.00),
        ModelInfo("grok-3-mini", "Grok 3 Mini", "grok", 0.30, 0.50),
    ],
    "gemini": [
        ModelInfo("gemini-2.5-pro", "Gemini 2.5 Pro", "gemini", 1.25, 10.00),
        ModelInfo("gemini-2.5-flash", "Gemini 2.5 Flash", "gemini", 0.15, 0.60),
        ModelInfo("gemini-2.0-flash", "Gemini 2.0 Flash", "gemini", 0.10, 0.40),
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
