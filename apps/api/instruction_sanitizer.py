"""Sanitize user-provided custom instructions before storage.

Strips dangerous content (code blocks, URLs, injection patterns) and
returns a cleaned version with a list of warnings.
"""

import re

_MAX_LENGTH = 15000

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I), "prompt injection: ignore instructions"),
    (re.compile(r"ignore\s+(all\s+)?above\s+instructions", re.I), "prompt injection: ignore instructions"),
    (re.compile(r"disregard\s+(all\s+)?previous", re.I), "prompt injection: disregard previous"),
    (re.compile(r"you\s+are\s+now\s+a", re.I), "prompt injection: role override"),
    (re.compile(r"act\s+as\s+(if\s+you\s+are\s+)?a", re.I), "prompt injection: role override"),
    (re.compile(r"pretend\s+(to\s+be|you\s+are)", re.I), "prompt injection: role override"),
    (re.compile(r"(reveal|show|print|output)\s+(your\s+)?(system\s+)?prompt", re.I), "prompt injection: reveal prompt"),
    (re.compile(r"what\s+(are|is)\s+your\s+(system\s+)?instructions", re.I), "prompt injection: reveal prompt"),
    (re.compile(r"override\s+(your\s+)?(rules|instructions|guidelines)", re.I), "prompt injection: override rules"),
    (re.compile(r"new\s+instructions?\s*:", re.I), "prompt injection: new instructions"),
    (re.compile(r"\bsystem\s*:\s*", re.I), "prompt injection: system role"),
    (re.compile(r"\bassistant\s*:\s*", re.I), "prompt injection: assistant role"),
    (re.compile(r"\buser\s*:\s*", re.I), "prompt injection: user role"),
    (re.compile(r"<\s*/?system\s*>", re.I), "prompt injection: XML system tags"),
    (re.compile(r"\{\"role\"\s*:\s*\"system\"", re.I), "prompt injection: JSON role injection"),
]

# Code block pattern (```lang ... ```)
_CODE_BLOCK_RE = re.compile(
    r"```(?:python|javascript|js|bash|sh|shell|ruby|perl|php|sql|cmd|powershell)"
    r"[\s\S]*?```",
    re.I,
)

# URL pattern
_URL_RE = re.compile(
    r"https?://[^\s<>\"')\]]+",
    re.I,
)

# Control characters (except newline/tab)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_instructions(text: str) -> tuple[str, list[str]]:
    """Sanitize custom instructions text.

    Returns:
        (sanitized_text, warnings) — warnings list contains reasons for any
        modifications made. If warnings contains an item starting with
        "REJECTED:", the instructions should be rejected entirely.
    """
    if not text:
        return "", []

    warnings: list[str] = []

    # Strip control characters
    cleaned = _CONTROL_CHARS_RE.sub("", text)

    # Check for injection patterns (reject on match)
    for pattern, reason in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            return "", [f"REJECTED: {reason}"]

    # Strip executable code blocks
    stripped, code_count = _CODE_BLOCK_RE.subn("[code block removed]", cleaned)
    if code_count:
        warnings.append(f"Removed {code_count} code block(s)")
        cleaned = stripped

    # Strip URLs
    stripped, url_count = _URL_RE.subn("[link removed]", cleaned)
    if url_count:
        warnings.append(f"Removed {url_count} URL(s)")
        cleaned = stripped

    # Enforce max length
    if len(cleaned) > _MAX_LENGTH:
        cleaned = cleaned[:_MAX_LENGTH]
        warnings.append(f"Truncated to {_MAX_LENGTH} characters")

    return cleaned.strip(), warnings
