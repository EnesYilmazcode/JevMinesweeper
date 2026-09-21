"""Deterministic beginner Minesweeper with a guaranteed safe center opening."""
from collections import deque

import numpy as np

ROWS = COLS = 9
N_MINES = 10
COVERED, MINE = -1, -2
CENTER = (ROWS // 2, COLS // 2)


def neighbors(cell):
    r, c = cell
    return [(rr, cc) for rr in range(max(0, r - 1), min(ROWS, r + 2))
            for cc in range(max(0, c - 1), min(COLS, c + 2)) if (rr, cc) != cell]


class Game:
    def __init__(self, seed, n_mines=N_MINES, opening_radius=1):
        self.seed = int(seed)
        self.n_mines = int(n_mines)
        self.opening_radius = int(opening_radius)
        rng = np.random.default_rng(seed)
        forbidden = {(r, c) for r in range(ROWS) for c in range(COLS)
                     if abs(r - CENTER[0]) <= self.opening_radius and abs(c - CENTER[1]) <= self.opening_radius}
        choices = [i for i in range(ROWS * COLS) if divmod(i, COLS) not in forbidden]
        picked = rng.choice(choices, self.n_mines, replace=False)
        self.mines = np.zeros((ROWS, COLS), bool)
        self.mines.flat[picked] = True
        self.clues = np.zeros((ROWS, COLS), np.int8)
        for r in range(ROWS):
            for c in range(COLS):
                self.clues[r, c] = sum(self.mines[x] for x in neighbors((r, c)))
        self.revealed = np.zeros((ROWS, COLS), bool)
        self.exploded = None
        self.moves = []
        self.click(CENTER)

    def click(self, cell):
        cell = tuple(cell)
        if self.over or self.revealed[cell]:
            raise ValueError(f"illegal click {cell}")
        self.moves.append(cell)
        if self.mines[cell]:
            self.exploded = cell
            return []
        opened, queue = [], deque([cell])
        while queue:
            here = queue.popleft()
            if self.revealed[here] or self.mines[here]:
                continue
            self.revealed[here] = True
            opened.append(here)
            if self.clues[here] == 0:
                queue.extend(neighbors(here))
        return opened

    @property
    def won(self):
        return int(self.revealed.sum()) == ROWS * COLS - self.n_mines

    @property
    def over(self):
        return self.exploded is not None or self.won

    @property
    def safe_revealed(self):
        return int(self.revealed.sum())

    def legal_cells(self):
        return [tuple(x) for x in np.argwhere(~self.revealed)] if not self.over else []

    def visible(self):
        board = np.full((ROWS, COLS), COVERED, np.int8)
        board[self.revealed] = self.clues[self.revealed]
        if self.exploded is not None:
            board[self.exploded] = MINE
        return board

    def record(self):
        return {"seed": self.seed, "won": self.won, "safe_revealed": self.safe_revealed,
                "n_mines": self.n_mines, "opening_radius": self.opening_radius, "n_clicks": len(self.moves),
                "moves": [[int(x[0]), int(x[1])] for x in self.moves[1:]]}


def replay(seed, moves, n_mines=N_MINES, opening_radius=1):
    game = Game(seed, n_mines=n_mines, opening_radius=opening_radius)
    states = [{"visible": game.visible().copy(), "opened": np.argwhere(game.revealed).tolist(),
               "clicked": CENTER, "won": game.won, "exploded": None}]
    for move in moves:
        opened = game.click(tuple(move))
        states.append({"visible": game.visible().copy(), "opened": [list(x) for x in opened],
                       "clicked": tuple(move), "won": game.won, "exploded": game.exploded})
    if not game.over:
        raise AssertionError("saved game does not reach a terminal state")
    return game, states
