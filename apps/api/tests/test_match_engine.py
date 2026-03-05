from match_engine import TERMINAL_STATES, VALID_TRANSITIONS, can_transition


def test_scheduled_to_in_progress():
    assert can_transition("scheduled", "in_progress") is True


def test_in_progress_to_completed():
    assert can_transition("in_progress", "completed") is True


def test_in_progress_to_forfeit():
    assert can_transition("in_progress", "forfeit") is True


def test_in_progress_to_aborted():
    assert can_transition("in_progress", "aborted") is True


def test_scheduled_to_completed_invalid():
    assert can_transition("scheduled", "completed") is False


def test_completed_to_anything_invalid():
    assert can_transition("completed", "in_progress") is False
    assert can_transition("completed", "forfeit") is False


def test_unknown_state_returns_false():
    assert can_transition("nonexistent", "in_progress") is False


def test_terminal_states():
    assert "completed" in TERMINAL_STATES
    assert "forfeit" in TERMINAL_STATES
    assert "aborted" in TERMINAL_STATES
    assert "scheduled" not in TERMINAL_STATES
    assert "in_progress" not in TERMINAL_STATES


def test_valid_transitions_cover_all_non_terminal():
    for state in VALID_TRANSITIONS:
        assert state not in TERMINAL_STATES
