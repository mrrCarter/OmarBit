"""Tests for opening_book module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opening_book import detect_opening


def test_sicilian_najdorf():
    moves = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]
    result = detect_opening(moves)
    assert result is not None
    assert result.eco == "B90"
    assert "Najdorf" in result.name


def test_ruy_lopez():
    moves = ["e4", "e5", "Nf3", "Nc6", "Bb5"]
    result = detect_opening(moves)
    assert result is not None
    assert result.eco == "C60"
    assert "Ruy Lopez" in result.name


def test_queens_gambit_declined():
    moves = ["d4", "d5", "c4", "e6"]
    result = detect_opening(moves)
    assert result is not None
    assert result.eco == "D30"
    assert "Queen's Gambit Declined" in result.name


def test_italian_game():
    moves = ["e4", "e5", "Nf3", "Nc6", "Bc4"]
    result = detect_opening(moves)
    assert result is not None
    assert result.eco == "C50"
    assert "Italian" in result.name


def test_sicilian_dragon():
    moves = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6"]
    result = detect_opening(moves)
    assert result is not None
    assert "Dragon" in result.name


def test_french_defense():
    moves = ["e4", "e6"]
    result = detect_opening(moves)
    assert result is not None
    assert result.eco == "C00"
    assert "French" in result.name


def test_caro_kann():
    moves = ["e4", "c6"]
    result = detect_opening(moves)
    assert result is not None
    assert result.eco == "B10"
    assert "Caro-Kann" in result.name


def test_kings_indian():
    moves = ["d4", "Nf6", "c4", "g6"]
    result = detect_opening(moves)
    assert result is not None
    assert result.eco == "E60"
    assert "King's Indian" in result.name


def test_london_system():
    moves = ["d4", "d5", "Nf3", "Nf6", "Bf4"]
    result = detect_opening(moves)
    assert result is not None
    assert "London" in result.name


def test_scholars_mate_partial():
    # 1.e4 e5 is Kings Pawn Game
    moves = ["e4", "e5"]
    result = detect_opening(moves)
    assert result is not None
    assert result.eco == "C20"


def test_empty_moves():
    result = detect_opening([])
    assert result is None


def test_single_move():
    result = detect_opening(["e4"])
    # Should not match anything (no single-move openings except b4, b3, f4)
    # e4 alone is not in our database
    assert result is None


def test_specific_match_longest():
    """Should return the most specific (longest) match."""
    moves = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]
    result = detect_opening(moves)
    # Should match Najdorf (B90) not just Sicilian (B20)
    assert result is not None
    assert result.eco == "B90"
