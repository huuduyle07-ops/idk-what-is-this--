import copy

FACES = ["U", "R", "F", "D", "L", "B"]
_COLORS = {"U": "W", "R": "r", "F": "G", "D": "Y", "L": "O", "B": "b"}

INVERSE_MAP = {
    "R": "R'", "R'": "R",
    "U": "U'", "U'": "U",
    "F": "F'", "F'": "F",
}


def solved_cube():
    return {face: [_COLORS[face]] * 9 for face in FACES}


def is_solved(cube):
    return cube == solved_cube()


def _rotate_cw(f):
    return [f[6], f[3], f[0], f[7], f[4], f[1], f[8], f[5], f[2]]


def _apply_R(cube):
    c = copy.deepcopy(cube)
    # U[2,5,8] -> F[2,5,8] -> D[2,5,8] -> B[6,3,0] -> U[2,5,8]
    c["F"][2], c["F"][5], c["F"][8] = cube["U"][2], cube["U"][5], cube["U"][8]
    c["D"][2], c["D"][5], c["D"][8] = cube["F"][2], cube["F"][5], cube["F"][8]
    c["B"][6], c["B"][3], c["B"][0] = cube["D"][2], cube["D"][5], cube["D"][8]
    c["U"][2], c["U"][5], c["U"][8] = cube["B"][6], cube["B"][3], cube["B"][0]
    c["R"] = _rotate_cw(cube["R"])
    return c


def _apply_U(cube):
    c = copy.deepcopy(cube)
    # F[0,1,2] -> R[0,1,2] -> B[0,1,2] -> L[0,1,2] -> F[0,1,2]
    c["R"][0], c["R"][1], c["R"][2] = cube["F"][0], cube["F"][1], cube["F"][2]
    c["B"][0], c["B"][1], c["B"][2] = cube["R"][0], cube["R"][1], cube["R"][2]
    c["L"][0], c["L"][1], c["L"][2] = cube["B"][0], cube["B"][1], cube["B"][2]
    c["F"][0], c["F"][1], c["F"][2] = cube["L"][0], cube["L"][1], cube["L"][2]
    c["U"] = _rotate_cw(cube["U"])
    return c


def _apply_F(cube):
    c = copy.deepcopy(cube)
    # U[6,7,8] -> R[0,3,6] -> D[2,1,0] -> L[8,5,2] -> U[6,7,8]
    c["R"][0], c["R"][3], c["R"][6] = cube["U"][6], cube["U"][7], cube["U"][8]
    c["D"][2], c["D"][1], c["D"][0] = cube["R"][0], cube["R"][3], cube["R"][6]
    c["L"][8], c["L"][5], c["L"][2] = cube["D"][2], cube["D"][1], cube["D"][0]
    c["U"][6], c["U"][7], c["U"][8] = cube["L"][8], cube["L"][5], cube["L"][2]
    c["F"] = _rotate_cw(cube["F"])
    return c


_BASE = {"R": _apply_R, "U": _apply_U, "F": _apply_F}


def apply_move(cube, move):
    fn = _BASE[move[0]]
    times = 3 if move.endswith("'") else 1
    c = cube
    for _ in range(times):
        c = fn(c)
    return c


def apply_sequence(cube, moves):
    c = cube
    for move in moves:
        c = apply_move(c, move)
    return c


def inverse_sequence(moves):
    return [INVERSE_MAP[m] for m in moves]  # BUG: should use reversed(moves)
