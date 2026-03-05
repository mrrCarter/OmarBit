"""Round-robin tournament scheduler.

Generates pairings for all active AI profiles in a round-robin format.
Per spec: automated round-robin scheduler over active AIs.
"""

import logging
import uuid
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MatchPairing:
    """A single match pairing between two AIs."""

    white_ai_id: str
    black_ai_id: str
    round_number: int


def generate_round_robin(ai_ids: list[str]) -> list[MatchPairing]:
    """Generate round-robin pairings for a list of AI IDs.

    Each AI plays every other AI exactly once (as white).
    For a full tournament, run twice with colors swapped.

    Returns pairings grouped by round using the circle method.
    """
    if len(ai_ids) < 2:
        return []

    ids = list(ai_ids)
    # If odd number, add a bye placeholder
    if len(ids) % 2 != 0:
        ids.append("__BYE__")

    n = len(ids)
    rounds = n - 1
    pairings: list[MatchPairing] = []

    # Circle method for round-robin scheduling
    fixed = ids[0]
    rotating = ids[1:]

    for round_num in range(rounds):
        current = [fixed] + rotating
        for i in range(n // 2):
            white = current[i]
            black = current[n - 1 - i]
            if white == "__BYE__" or black == "__BYE__":
                continue
            pairings.append(MatchPairing(
                white_ai_id=white,
                black_ai_id=black,
                round_number=round_num + 1,
            ))
        # Rotate
        rotating = [rotating[-1]] + rotating[:-1]

    return pairings


def generate_tournament_id() -> str:
    """Generate a unique tournament ID."""
    return str(uuid.uuid4())


def schedule_tournament(ai_ids: list[str]) -> dict:
    """Generate a full tournament schedule.

    Returns tournament metadata including all pairings.
    """
    tournament_id = generate_tournament_id()
    pairings = generate_round_robin(ai_ids)

    total_rounds = max((p.round_number for p in pairings), default=0)

    rounds: dict[int, list[dict]] = {}
    for p in pairings:
        if p.round_number not in rounds:
            rounds[p.round_number] = []
        rounds[p.round_number].append({
            "white_ai_id": p.white_ai_id,
            "black_ai_id": p.black_ai_id,
        })

    logger.info(
        "Tournament %s scheduled: %d AIs, %d rounds, %d matches",
        tournament_id,
        len(ai_ids),
        total_rounds,
        len(pairings),
    )

    return {
        "tournament_id": tournament_id,
        "ai_count": len(ai_ids),
        "total_rounds": total_rounds,
        "total_matches": len(pairings),
        "rounds": rounds,
    }
