"""Tests for ELO rating calculator."""

import pytest

from elo import DEFAULT_RATING, K_FACTOR, calculate_new_ratings, expected_score


def test_default_rating():
    assert DEFAULT_RATING == 1200


def test_k_factor():
    assert K_FACTOR == 32


def test_expected_score_equal_ratings():
    score = expected_score(1200, 1200)
    assert abs(score - 0.5) < 0.001


def test_expected_score_higher_rating_favored():
    score = expected_score(1400, 1200)
    assert score > 0.5


def test_expected_score_lower_rating_unfavored():
    score = expected_score(1000, 1200)
    assert score < 0.5


def test_expected_scores_sum_to_one():
    a = expected_score(1300, 1100)
    b = expected_score(1100, 1300)
    assert abs(a + b - 1.0) < 0.001


def test_white_win():
    new_w, new_b = calculate_new_ratings(1200, 1200, "white_win")
    assert new_w > 1200
    assert new_b < 1200
    assert new_w + new_b == 2400  # Zero-sum


def test_black_win():
    new_w, new_b = calculate_new_ratings(1200, 1200, "black_win")
    assert new_w < 1200
    assert new_b > 1200


def test_draw_equal_ratings():
    new_w, new_b = calculate_new_ratings(1200, 1200, "draw")
    assert new_w == 1200
    assert new_b == 1200


def test_draw_unequal_ratings():
    new_w, new_b = calculate_new_ratings(1400, 1000, "draw")
    # Higher rated player loses points on draw
    assert new_w < 1400
    assert new_b > 1000


def test_upset_gives_more_points():
    # Lower rated player (1000) beating higher rated (1400)
    new_w, new_b = calculate_new_ratings(1000, 1400, "white_win")
    gain_w = new_w - 1000
    # Compare with expected win
    new_w2, _ = calculate_new_ratings(1400, 1000, "white_win")
    gain_w2 = new_w2 - 1400
    # Upset gives more points
    assert gain_w > gain_w2


def test_invalid_result():
    with pytest.raises(ValueError, match="Invalid result"):
        calculate_new_ratings(1200, 1200, "invalid")


def test_ratings_are_integers():
    new_w, new_b = calculate_new_ratings(1234, 1567, "white_win")
    assert isinstance(new_w, int)
    assert isinstance(new_b, int)
