"""API key validation — lightweight test call to verify a key works."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Skip real API calls in local dev (set SKIP_KEY_VALIDATION=true, or NODE_ENV=development).
_SKIP_VALIDATION = (
    os.getenv("SKIP_KEY_VALIDATION", "").lower() == "true"
    or os.getenv("NODE_ENV", "").lower() == "development"
)

_TIMEOUT = httpx.Timeout(5.0, read=10.0)


async def validate_api_key(provider: str, model: str, api_key: str) -> tuple[bool, str]:
    """Test an API key with a minimal request. Returns (valid, error_message)."""
    if _SKIP_VALIDATION:
        logger.info("Skipping API key validation (SKIP_KEY_VALIDATION=true)")
        return True, ""
    try:
        if provider == "claude":
            return await _validate_claude(api_key, model)
        elif provider == "gpt":
            return await _validate_openai(api_key, model)
        elif provider == "grok":
            return await _validate_grok(api_key, model)
        elif provider == "gemini":
            return await _validate_gemini(api_key, model)
        else:
            return False, f"Unknown provider: {provider}"
    except httpx.TimeoutException:
        return False, "Validation timed out — key may still be valid"
    except Exception as exc:
        logger.warning("Key validation error for %s: %s", provider, exc)
        return False, f"Validation error: {type(exc).__name__}"


async def _validate_claude(api_key: str, model: str) -> tuple[bool, str]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    return _check_status(resp, "Claude")


async def _validate_openai(api_key: str, model: str) -> tuple[bool, str]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    return _check_status(resp, "OpenAI")


async def _validate_grok(api_key: str, model: str) -> tuple[bool, str]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    return _check_status(resp, "xAI")


async def _validate_gemini(api_key: str, model: str) -> tuple[bool, str]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": "hi"}]}],
                "generationConfig": {"maxOutputTokens": 1},
            },
        )
    return _check_status(resp, "Gemini")


def _check_status(resp: httpx.Response, name: str) -> tuple[bool, str]:
    if resp.status_code in (200, 201):
        return True, ""
    if resp.status_code in (401, 403):
        return False, f"Invalid API key for {name}"
    if resp.status_code == 429:
        return False, f"{name} quota exhausted — try again later"
    if resp.status_code == 404:
        return False, f"Model not found on {name}"
    return False, f"{name} returned status {resp.status_code}"
