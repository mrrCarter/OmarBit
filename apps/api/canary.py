"""Canary / progressive rollout evaluation.

Evaluates feature flags with rollout_percent for progressive delivery.
Per spec: canary flag rollout.
"""

import hashlib
import logging

logger = logging.getLogger(__name__)


def evaluate_rollout(
    flag_key: str,
    user_id: str,
    rollout_percent: int,
    enabled: bool,
) -> bool:
    """Evaluate whether a user is in the rollout for a feature flag.

    Uses a deterministic hash of (flag_key, user_id) to assign users
    consistently to a rollout bucket. This ensures:
    - Same user always gets same result for same flag
    - Progressive rollout from 0% to 100% is monotonic (users in 30%
      are always in 50%)

    Args:
        flag_key: The feature flag key.
        user_id: The user's ID (UUID string).
        rollout_percent: 0-100, the percentage of users to include.
        enabled: Whether the flag is globally enabled.

    Returns:
        True if the user should see the feature.
    """
    if not enabled:
        return False

    if rollout_percent >= 100:
        return True

    if rollout_percent <= 0:
        return False

    # Deterministic bucket assignment
    hash_input = f"{flag_key}:{user_id}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    bucket = int.from_bytes(hash_bytes[:2], "big") % 100

    return bucket < rollout_percent
