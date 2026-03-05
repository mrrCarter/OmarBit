"""Tests for round-robin tournament scheduler."""

from scheduler import MatchPairing, generate_round_robin, schedule_tournament


def test_two_ais():
    pairings = generate_round_robin(["a", "b"])
    assert len(pairings) == 1
    assert pairings[0].white_ai_id == "a"
    assert pairings[0].black_ai_id == "b"
    assert pairings[0].round_number == 1


def test_three_ais():
    pairings = generate_round_robin(["a", "b", "c"])
    # With 3 AIs (odd), one gets a bye each round
    # 3 rounds, 1 match per round = 3 matches
    assert len(pairings) == 3
    # Each AI appears in exactly 2 matches
    counts: dict[str, int] = {}
    for p in pairings:
        counts[p.white_ai_id] = counts.get(p.white_ai_id, 0) + 1
        counts[p.black_ai_id] = counts.get(p.black_ai_id, 0) + 1
    assert all(c == 2 for c in counts.values())


def test_four_ais():
    pairings = generate_round_robin(["a", "b", "c", "d"])
    # 4 AIs: 3 rounds, 2 matches per round = 6 matches
    assert len(pairings) == 6
    # Each pair plays exactly once
    pairs = {(p.white_ai_id, p.black_ai_id) for p in pairings}
    assert len(pairs) == 6


def test_empty_list():
    assert generate_round_robin([]) == []


def test_single_ai():
    assert generate_round_robin(["a"]) == []


def test_round_numbers_assigned():
    pairings = generate_round_robin(["a", "b", "c", "d"])
    rounds = {p.round_number for p in pairings}
    assert rounds == {1, 2, 3}


def test_schedule_tournament_structure():
    result = schedule_tournament(["a", "b", "c"])
    assert "tournament_id" in result
    assert result["ai_count"] == 3
    assert result["total_rounds"] > 0
    assert result["total_matches"] > 0
    assert "rounds" in result
    assert isinstance(result["rounds"], dict)


def test_schedule_tournament_empty():
    result = schedule_tournament([])
    assert result["total_matches"] == 0
    assert result["total_rounds"] == 0


def test_match_pairing_frozen():
    p = MatchPairing(white_ai_id="a", black_ai_id="b", round_number=1)
    assert p.white_ai_id == "a"
    try:
        p.white_ai_id = "c"  # type: ignore
        assert False, "Should be frozen"
    except AttributeError:
        pass


def test_six_ais_complete_round_robin():
    ids = [f"ai-{i}" for i in range(6)]
    pairings = generate_round_robin(ids)
    # 6 AIs: C(6,2) = 15 unique pairings
    assert len(pairings) == 15
    # 5 rounds
    rounds = {p.round_number for p in pairings}
    assert len(rounds) == 5
