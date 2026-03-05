"""Match lifecycle state machine.

Valid transitions:
  scheduled -> in_progress
  in_progress -> completed | forfeit | aborted
"""

VALID_TRANSITIONS: dict[str, set[str]] = {
    "scheduled": {"in_progress"},
    "in_progress": {"completed", "forfeit", "aborted"},
}


def can_transition(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, set())


TERMINAL_STATES = frozenset({"completed", "forfeit", "aborted"})
