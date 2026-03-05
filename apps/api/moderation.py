"""Chat line moderation filter per spec Section 5.1.

Policy: teen-safe (13+). Blocks hate, sexual, violence, self-harm, PII, prompt injection.
Rate limits: max 1 chat line per move, max 280 chars, 3 strikes => muted.
Language: English-only MVP.
"""

import logging
import re

logger = logging.getLogger(__name__)

_MAX_CHAT_LENGTH = 280
_MAX_STRIKES = 3

# Blocklist patterns — kept intentionally minimal; a production system would
# use a more comprehensive list or external service.
_BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    # Prompt injection attempts
    re.compile(r"ignore\s+(previous|above|all)\s+(instructions?|prompts?)", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    # PII patterns
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    # Explicit slurs and severe profanity (minimal set — extend in production)
    re.compile(r"\b(kill\s+yourself|kys)\b", re.IGNORECASE),
]

FILTERED_REPLACEMENT = "[message filtered]"


def moderate_chat_line(
    chat_line: str,
    strike_count: int,
) -> tuple[str, bool, str | None]:
    """Filter a chat line per moderation matrix.

    Args:
        chat_line: The raw chat line from the provider.
        strike_count: Current strike count for this AI in this match.

    Returns:
        Tuple of (filtered_line, was_blocked, violation_reason).
        If muted (>= 3 strikes), returns empty string.
    """
    if strike_count >= _MAX_STRIKES:
        return "", True, "AI muted (3-strike limit reached)"

    if not chat_line or not chat_line.strip():
        return "", False, None

    # Enforce length limit
    line = chat_line[:_MAX_CHAT_LENGTH]

    # Check blocklist
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(line):
            reason = f"Blocked pattern: {pattern.pattern}"
            logger.warning("Moderation blocked chat line: %s", reason)
            return FILTERED_REPLACEMENT, True, reason

    return line, False, None
