"""ELO rating calculator.

Implements standard ELO with K=32 for the MVP.
Per spec: ELO updates transactionally once per match.
"""

import math

K_FACTOR = 32
DEFAULT_RATING = 1200


def expected_score(rating_a: int, rating_b: int) -> float:
    """Calculate expected score for player A against player B."""
    return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))


def calculate_new_ratings(
    rating_white: int,
    rating_black: int,
    result: str,
) -> tuple[int, int]:
    """Calculate new ELO ratings after a match.

    Args:
        rating_white: Current ELO of the white player.
        rating_black: Current ELO of the black player.
        result: One of "white_win", "black_win", "draw".

    Returns:
        Tuple of (new_white_rating, new_black_rating).
    """
    e_white = expected_score(rating_white, rating_black)
    e_black = 1.0 - e_white

    if result == "white_win":
        s_white, s_black = 1.0, 0.0
    elif result == "black_win":
        s_white, s_black = 0.0, 1.0
    elif result == "draw":
        s_white, s_black = 0.5, 0.5
    else:
        raise ValueError(f"Invalid result: {result!r}")

    new_white = round(rating_white + K_FACTOR * (s_white - e_white))
    new_black = round(rating_black + K_FACTOR * (s_black - e_black))

    return new_white, new_black
