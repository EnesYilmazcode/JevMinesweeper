"""Visible-information Minesweeper teacher using constraint and subset deductions."""
import numpy as np

from .game import COVERED, N_MINES, neighbors


def constraints(board):
    equations = {}
    known_mines, known_safe = set(), set()
    changed = True
    while changed:
        changed = False
        equations = {}
        for r, c in np.argwhere(board >= 0):
            unknown = frozenset(x for x in neighbors((int(r), int(c)))
                                if board[x] == COVERED and x not in known_mines and x not in known_safe)
            remaining = int(board[r, c]) - sum(x in known_mines for x in neighbors((int(r), int(c))))
            if unknown:
                equations[unknown] = remaining
        items = list(equations.items())
        for cells, count in items:
            if count == 0:
                add = set(cells) - known_safe
                known_safe |= add
                changed |= bool(add)
            elif count == len(cells):
                add = set(cells) - known_mines
                known_mines |= add
                changed |= bool(add)
        items = list(equations.items())
        for a, av in items:
            for b, bv in items:
                if a != b and a < b:
                    diff, value = b - a, bv - av
                    if value == 0:
                        add = set(diff) - known_safe
                        known_safe |= add
                        changed |= bool(add)
                    elif value == len(diff):
                        add = set(diff) - known_mines
                        known_mines |= add
                        changed |= bool(add)
    return known_safe, known_mines, equations


def risks(board):
    """Estimated mine probability for every covered cell, using no hidden information."""
    safe, mines, equations = constraints(board)
    covered = [tuple(x) for x in np.argwhere(board == COVERED)]
    remaining_global = max(0, N_MINES - len(mines))
    unresolved = [x for x in covered if x not in safe and x not in mines]
    base = remaining_global / max(1, len(unresolved))
    out = {}
    for cell in covered:
        if cell in safe:
            out[cell] = 0.0
        elif cell in mines:
            out[cell] = 1.0
        else:
            local = [n / len(cells) for cells, n in equations.items() if cell in cells]
            out[cell] = max(local) if local else base
    return out


def action_values(board):
    out = {}
    for cell, risk in risks(board).items():
        revealed_neighbors = sum(board[x] >= 0 for x in neighbors(cell))
        covered_neighbors = sum(board[x] == COVERED for x in neighbors(cell))
        out[cell] = -10.0 * risk + 0.05 * revealed_neighbors + 0.005 * covered_neighbors
    return out


def teacher_move(board):
    values = action_values(board)
    return max(values, key=lambda x: (values[x], -x[0], -x[1])) if values else None

