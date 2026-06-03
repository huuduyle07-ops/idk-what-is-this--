# Design: python_rubiks_inverse_sequence_trap

**Date:** 2026-06-03  
**Status:** Approved (Option B)

---

## Goal

Add an algorithm benchmark case that tests whether an agent can fix a Rubik's Cube move-simulator bug using property-style validation, without overfitting to one failing example.

---

## Bug Shape

`inverse_sequence(moves)` in `cube.py` iterates `moves` in **forward order** instead of `reversed(moves)`.

```python
# Buggy
def inverse_sequence(moves):
    return [INVERSE_MAP[m] for m in moves]

# Fixed
def inverse_sequence(moves):
    return [INVERSE_MAP[m] for m in reversed(moves)]
```

**Why this is a trap:** For a single-move list `[R]`, forward and reversed iteration produce the same result, so tests 1–2 and 5–6 all pass with the bug. Only multi-move sequence tests (3, 4) fail. An agent that patches the output of one specific scramble will still fail the second scramble test.

The property being enforced: `(AB)⁻¹ = B⁻¹A⁻¹` — the inverse of a composed sequence reverses order.

---

## Cube Representation

- State: `dict[str, list[str]]` — six faces `U R F D L B`, each holding 9 single-character color codes.
- Color codes: `W` (white/U), `r` (red/R), `G` (green/F), `Y` (yellow/D), `O` (orange/L), `b` (blue/B). Lowercase `r` and `b` avoid ambiguity with face names `R` and `B`.
- Moves implemented: **R, U, F** (clockwise, and prime = 3× clockwise).
- No external libraries; only stdlib `copy`.

### R clockwise sticker cycle

```
U[2,5,8] → F[2,5,8] → D[2,5,8] → B[6,3,0] → U[2,5,8]
```
(B column is reversed relative to the others — standard cube convention.)

### U clockwise sticker cycle

```
F[0,1,2] → R[0,1,2] → B[0,1,2] → L[0,1,2] → F[0,1,2]
```

### F clockwise sticker cycle

```
U[6,7,8] → R[0,3,6] → D[2,1,0] → L[8,5,2] → U[6,7,8]
```

---

## Public API in `cube.py`

| Function | Purpose |
|---|---|
| `solved_cube()` | Returns a fresh solved cube dict |
| `is_solved(cube)` | True iff cube == solved_cube() |
| `apply_move(cube, move)` | Applies one named move, returns new cube (deepcopy) |
| `apply_sequence(cube, moves)` | Applies each move in order, returns final cube |
| `inverse_sequence(moves)` | **Buggy here** — returns list of inverse move names |

---

## Validation Tests (`test_cube.py`)

Run with: `python -m pytest -q`

| Test | Description | Passes with bug? |
|---|---|---|
| `test_empty_sequence` | `apply_sequence(solved, []) == solved` | ✓ |
| `test_single_move_inverse_R` | R then R′ → solved | ✓ |
| `test_single_move_inverse_U` | U then U′ → solved | ✓ |
| `test_single_move_inverse_F` | F then F′ → solved | ✓ |
| `test_scramble_inverse_RU` | [R, U] then inverse([R, U]) → solved | **✗** |
| `test_scramble_inverse_FRU` | [F, R, U] then inverse([F, R, U]) → solved | **✗** |
| `test_four_R_is_identity` | R×4 → solved | ✓ |
| `test_known_R_state` | After R: `U[2]=='b'`, `F[2]=='W'`, `D[2]=='G'` | ✓ |

Tests 5 and 6 use different sequences. Hardcoding the inverse for one will not fix the other.

---

## File Layout

```
benchmarks/cases/python/python_rubiks_inverse_sequence_trap/
  case.json
  buggy_repo/
    cube.py        ← expected_changed_files: ["cube.py"]
    test_cube.py   ← forbidden_changed_files: ["test_cube.py"]
```

### case.json key fields

```json
{
  "name": "python_rubiks_inverse_sequence_trap",
  "language": "python",
  "category": "algorithm",
  "difficulty": "hard",
  "agent_mode": "reviewer",
  "patch_style": "balanced",
  "validation_command": "python -m pytest -q",
  "expected_changed_files": ["cube.py"],
  "forbidden_changed_files": ["test_cube.py"],
  "allowed_generated_files": []
}
```

---

## Suite Registry Changes

| Suite | Action |
|---|---|
| `full_v1.json` | Add `python_rubiks_inverse_sequence_trap`; update description (41 → 42); update description text |
| `held_out_v1.json` | Add `python_rubiks_inverse_sequence_trap` (adversarial/hard cases) |
| `dev_v1.json` | No change |

---

## Constraints

- No external packages beyond stdlib.
- No random tests (all deterministic).
- No `conftest.py` or extra files beyond `cube.py` + `test_cube.py`.
- The correct patch touches only `inverse_sequence` in `cube.py`; tests and metadata are immutable.
- `benchmark --check` count: 41 → 42.
