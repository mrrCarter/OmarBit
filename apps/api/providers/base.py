"""Base provider adapter interface and shared retry logic."""

import asyncio
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Spec Section 7: Timeout/Retry Matrix for all provider APIs
_CONNECT_TIMEOUT = 3.0
_READ_TIMEOUT = 20.0
_MAX_RETRIES = 2
_BACKOFF_SCHEDULE = (0.5, 1.0)


@dataclass(frozen=True, slots=True)
class MoveResponse:
    """Structured response from a provider move request."""

    san: str
    think_summary: str
    chat_line: str


class ProviderError(Exception):
    """Base for provider-specific errors."""


class QuotaExhaustedError(ProviderError):
    """Raised when the provider returns 429 or quota-related error."""


class ProviderUnavailableError(ProviderError):
    """Raised when provider is unreachable after retries."""


class InvalidResponseError(ProviderError):
    """Raised when provider response cannot be parsed."""


class BaseProvider:
    """Abstract base for AI provider adapters.

    Subclasses must implement:
      - _build_request(fen, legal_moves, style, match_context) -> (url, headers, body)
      - _parse_response(data) -> MoveResponse
    """

    provider_name: str = "base"

    def _build_request(
        self,
        api_key: str,
        fen: str,
        legal_moves: list[str],
        style: str,
        match_context: dict,
    ) -> tuple[str, dict, dict]:
        raise NotImplementedError

    def _parse_response(self, data: dict) -> MoveResponse:
        raise NotImplementedError

    async def request_move(
        self,
        api_key: str,
        fen: str,
        legal_moves: list[str],
        style: str,
        match_context: dict | None = None,
    ) -> MoveResponse:
        """Request a move from the provider with spec-compliant retry/backoff."""
        context = match_context or {}
        url, headers, body = self._build_request(api_key, fen, legal_moves, style, context)

        last_err: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT),
                ) as client:
                    resp = await client.post(url, headers=headers, json=body)

                    if resp.status_code == 429:
                        raise QuotaExhaustedError(
                            f"{self.provider_name} quota exhausted (429)"
                        )

                    if resp.status_code in (401, 403):
                        raise ProviderError(
                            f"{self.provider_name} auth error ({resp.status_code}): "
                            f"check API key"
                        )

                    resp.raise_for_status()
                    data = resp.json()
                    return self._parse_response(data)

            except QuotaExhaustedError:
                raise
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_err = exc
                logger.warning(
                    "Provider %s attempt %d/%d failed: %s",
                    self.provider_name,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    exc,
                )
            except httpx.HTTPStatusError as exc:
                last_err = exc
                logger.warning(
                    "Provider %s attempt %d/%d HTTP %d",
                    self.provider_name,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    exc.response.status_code,
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise InvalidResponseError(
                    f"{self.provider_name} returned unparseable response: {exc}"
                ) from exc

            if attempt < _MAX_RETRIES:
                backoff = _BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)]
                await asyncio.sleep(backoff)

        raise ProviderUnavailableError(
            f"{self.provider_name} unavailable after {_MAX_RETRIES + 1} attempts: {last_err}"
        )
