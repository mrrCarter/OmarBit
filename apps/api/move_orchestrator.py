"""Move orchestrator — coordinates provider request, stockfish validation,
moderation, and persistence for a single ply.

Implements the forfeit-on-unrecoverable-error flow per spec Phase 3.
"""

import logging

import httpx

from moderation import moderate_chat_line
from providers.base import (
    InvalidResponseError,
    MoveResponse,
    ProviderError,
    ProviderUnavailableError,
    QuotaExhaustedError,
)
from providers.registry import get_provider
from stockfish import validate_move

logger = logging.getLogger(__name__)

# Max attempts to get a legal move from the provider before forfeiting
_MAX_ILLEGAL_MOVE_ATTEMPTS = 3


class MoveResult:
    """Result of a single move orchestration."""

    __slots__ = ("san", "think_summary", "chat_line", "forfeit", "forfeit_reason")

    def __init__(
        self,
        *,
        san: str = "",
        think_summary: str = "",
        chat_line: str = "",
        forfeit: bool = False,
        forfeit_reason: str = "",
    ) -> None:
        self.san = san
        self.think_summary = think_summary
        self.chat_line = chat_line
        self.forfeit = forfeit
        self.forfeit_reason = forfeit_reason


async def orchestrate_move(
    provider_name: str,
    api_key: str,
    fen: str,
    legal_moves: list[str],
    style: str,
    match_context: dict,
    strike_count: int = 0,
    client: httpx.AsyncClient | None = None,
) -> MoveResult:
    """Request, validate, and moderate a single move.

    Returns MoveResult with forfeit=True if the provider fails unrecoverably.

    Flow:
    1. Call provider adapter for a move
    2. Validate move legality via Stockfish
    3. If illegal, retry up to _MAX_ILLEGAL_MOVE_ATTEMPTS
    4. Moderate chat_line per Section 5.1
    5. Enforce thought-stream contract (Section 5.2): summary only, max 500 chars

    Forfeit triggers:
    - QuotaExhaustedError (429)
    - ProviderUnavailableError (all retries exhausted)
    - InvalidResponseError persists after retries
    - All move attempts produce illegal moves
    """
    provider = get_provider(provider_name)

    for attempt in range(_MAX_ILLEGAL_MOVE_ATTEMPTS):
        try:
            response: MoveResponse = await provider.request_move(
                api_key=api_key,
                fen=fen,
                legal_moves=legal_moves,
                style=style,
                match_context=match_context,
                client=client,
            )
        except QuotaExhaustedError as exc:
            logger.error("Quota exhausted for %s: %s", provider_name, exc)
            return MoveResult(
                forfeit=True,
                forfeit_reason=f"Provider quota exhausted ({provider_name})",
            )
        except ProviderUnavailableError as exc:
            logger.error("Provider unavailable %s: %s", provider_name, exc)
            return MoveResult(
                forfeit=True,
                forfeit_reason=f"Provider unavailable after retries ({provider_name})",
            )
        except InvalidResponseError as exc:
            logger.warning("Invalid response from %s (attempt %d): %s", provider_name, attempt + 1, exc)
            continue
        except ProviderError as exc:
            logger.error("Provider error %s: %s", provider_name, exc)
            return MoveResult(
                forfeit=True,
                forfeit_reason=f"AI engine error ({provider_name})",
            )

        # Validate the move is in the legal moves list (quick pre-check)
        if response.san not in legal_moves:
            logger.warning(
                "Provider %s returned illegal move %s (attempt %d/%d)",
                provider_name,
                response.san,
                attempt + 1,
                _MAX_ILLEGAL_MOVE_ATTEMPTS,
            )
            continue

        # Validate via Stockfish
        try:
            is_legal = await validate_move(fen, response.san)
        except RuntimeError:
            # Stockfish unavailable — trust the legal_moves pre-check
            logger.warning("Stockfish unavailable, trusting legal_moves list")
            is_legal = True

        if not is_legal:
            logger.warning(
                "Stockfish rejected move %s from %s (attempt %d/%d)",
                response.san,
                provider_name,
                attempt + 1,
                _MAX_ILLEGAL_MOVE_ATTEMPTS,
            )
            continue

        # Enforce thought-stream contract: summary only, max 500 chars
        think_summary = (response.think_summary or "")[:500]

        # Moderate chat line
        chat_line, was_blocked, _reason = moderate_chat_line(
            response.chat_line or "",
            strike_count,
        )

        return MoveResult(
            san=response.san,
            think_summary=think_summary,
            chat_line=chat_line,
        )

    # All attempts exhausted — forfeit
    return MoveResult(
        forfeit=True,
        forfeit_reason=(
            f"Provider {provider_name} failed to produce a legal move "
            f"after {_MAX_ILLEGAL_MOVE_ATTEMPTS} attempts"
        ),
    )
