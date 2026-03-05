"""Tests for game_loop module — unit tests with mocked DB/providers."""

import time

import chess

from game_loop import (
    MatchClock,
    _board_to_pgn,
    parse_time_control,
)

# --- MatchClock tests ---


def test_clock_initial_state():
    clock = MatchClock(white_time=300.0, black_time=300.0)
    assert clock.white_time == 300.0
    assert clock.black_time == 300.0
    assert clock.active_side == chess.WHITE


def test_clock_start_and_end_turn():
    clock = MatchClock(white_time=300.0, black_time=300.0)
    clock.start_turn()
    time.sleep(0.05)
    elapsed = clock.end_turn()
    assert elapsed > 0
    assert clock.white_time < 300.0
    assert clock.black_time == 300.0
    assert clock.active_side == chess.BLACK


def test_clock_alternates_sides():
    clock = MatchClock(white_time=300.0, black_time=300.0)
    assert clock.active_side == chess.WHITE
    clock.start_turn()
    clock.end_turn()
    assert clock.active_side == chess.BLACK
    clock.start_turn()
    clock.end_turn()
    assert clock.active_side == chess.WHITE


def test_clock_flagged():
    clock = MatchClock(white_time=0.0, black_time=300.0)
    clock.start_turn()
    assert clock.is_flagged() is True


def test_clock_not_flagged():
    clock = MatchClock(white_time=300.0, black_time=300.0)
    clock.start_turn()
    assert clock.is_flagged() is False


def test_clock_active_remaining():
    clock = MatchClock(white_time=100.0, black_time=200.0)
    clock.start_turn()
    remaining = clock.active_remaining()
    assert 99.0 < remaining <= 100.0


# --- parse_time_control tests ---


def test_parse_5_plus_0():
    initial, increment = parse_time_control("5+0")
    assert initial == 300.0
    assert increment == 0.0


def test_parse_3_plus_2():
    initial, increment = parse_time_control("3+2")
    assert initial == 180.0
    assert increment == 2.0


def test_parse_10_plus_5():
    initial, increment = parse_time_control("10+5")
    assert initial == 600.0
    assert increment == 5.0


def test_parse_invalid_falls_back():
    initial, increment = parse_time_control("invalid")
    assert initial == 300.0
    assert increment == 0.0


def test_parse_empty_falls_back():
    initial, increment = parse_time_control("")
    assert initial == 300.0
    assert increment == 0.0


# --- _board_to_pgn tests ---


def test_board_to_pgn_scholars_mate():
    board = chess.Board()
    moves = ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]
    for m in moves:
        board.push_san(m)
    pgn = _board_to_pgn(board, "WhiteBot", "BlackBot")
    assert "WhiteBot" in pgn
    assert "BlackBot" in pgn
    assert "OmarBit Arena" in pgn
    assert "1-0" in pgn


def test_board_to_pgn_empty_game():
    board = chess.Board()
    pgn = _board_to_pgn(board, "W", "B")
    assert "W" in pgn
    assert "B" in pgn


# --- Edge cases ---


class TestMatchClockEdgeCases:
    def test_zero_time_flags_immediately(self):
        clock = MatchClock(white_time=0.001, black_time=300.0)
        clock.start_turn()
        time.sleep(0.02)
        assert clock.is_flagged() is True

    def test_black_turn_flag(self):
        clock = MatchClock(white_time=300.0, black_time=0.0)
        clock.start_turn()
        clock.end_turn()  # White's turn done, now Black
        clock.start_turn()
        assert clock.is_flagged() is True

    def test_remaining_decreases(self):
        clock = MatchClock(white_time=10.0, black_time=10.0)
        clock.start_turn()
        r1 = clock.active_remaining()
        time.sleep(0.05)
        r2 = clock.active_remaining()
        assert r2 < r1
