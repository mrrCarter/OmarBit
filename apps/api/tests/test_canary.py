"""Tests for canary / progressive rollout evaluation."""

from canary import evaluate_rollout


def test_disabled_flag_always_false():
    assert evaluate_rollout("test", "user-1", 100, False) is False


def test_enabled_100_percent():
    assert evaluate_rollout("test", "user-1", 100, True) is True


def test_enabled_0_percent():
    assert evaluate_rollout("test", "user-1", 0, True) is False


def test_deterministic():
    r1 = evaluate_rollout("flag-a", "user-1", 50, True)
    r2 = evaluate_rollout("flag-a", "user-1", 50, True)
    assert r1 == r2


def test_different_users_different_results():
    # With 50% rollout, not all users should get the same result
    results = set()
    for i in range(100):
        results.add(evaluate_rollout("flag-test", f"user-{i}", 50, True))
    # Should have both True and False
    assert len(results) == 2


def test_monotonic_rollout():
    # Users in 30% should always be in 50%
    for i in range(50):
        user = f"user-{i}"
        if evaluate_rollout("flag", user, 30, True):
            assert evaluate_rollout("flag", user, 50, True)


def test_different_flags_different_buckets():
    # Same user, different flags should potentially get different results
    results = set()
    for i in range(20):
        results.add(evaluate_rollout(f"flag-{i}", "user-1", 50, True))
    # Should have variation
    assert len(results) == 2


def test_rollout_negative_treated_as_zero():
    assert evaluate_rollout("test", "user-1", -10, True) is False


def test_rollout_over_100_treated_as_100():
    assert evaluate_rollout("test", "user-1", 150, True) is True
