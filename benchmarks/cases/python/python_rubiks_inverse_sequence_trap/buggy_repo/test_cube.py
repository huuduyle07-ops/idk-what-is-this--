import pytest
from cube import solved_cube, is_solved, apply_move, apply_sequence, inverse_sequence


def test_empty_sequence():
    c = solved_cube()
    assert apply_sequence(c, []) == c


def test_single_move_inverse_R():
    c = solved_cube()
    result = apply_sequence(c, ["R", "R'"])
    assert is_solved(result)


def test_single_move_inverse_U():
    c = solved_cube()
    result = apply_sequence(c, ["U", "U'"])
    assert is_solved(result)


def test_single_move_inverse_F():
    c = solved_cube()
    result = apply_sequence(c, ["F", "F'"])
    assert is_solved(result)


def test_scramble_inverse_RU():
    c = solved_cube()
    moves = ["R", "U"]
    scrambled = apply_sequence(c, moves)
    restored = apply_sequence(scrambled, inverse_sequence(moves))
    assert is_solved(restored)


def test_scramble_inverse_FRU():
    c = solved_cube()
    moves = ["F", "R", "U"]
    scrambled = apply_sequence(c, moves)
    restored = apply_sequence(scrambled, inverse_sequence(moves))
    assert is_solved(restored)


def test_four_R_is_identity():
    c = solved_cube()
    result = apply_sequence(c, ["R", "R", "R", "R"])
    assert is_solved(result)


def test_known_R_state():
    c = solved_cube()
    result = apply_move(c, "R")
    assert result["U"][2] == "b"
    assert result["F"][2] == "W"
    assert result["D"][2] == "G"
