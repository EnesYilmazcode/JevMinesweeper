import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from minesweeper.game import CENTER, COVERED, Game, neighbors, replay
from minesweeper.solver import risks, teacher_move


def test_seed_is_deterministic_and_opening_is_safe():
    a, b = Game(17), Game(17)
    assert np.array_equal(a.mines, b.mines)
    assert not any(a.mines[x] for x in {CENTER, *neighbors(CENTER)})
    assert a.visible()[CENTER] == 0


def test_flood_reveal_and_loss():
    game = Game(2)
    assert game.safe_revealed >= 9
    mine = tuple(np.argwhere(game.mines)[0])
    game.click(mine)
    assert game.over and not game.won and game.visible()[mine] == -2


def test_solver_deductions_are_sound_on_seeded_games():
    for seed in range(20):
        game = Game(seed)
        for _ in range(30):
            if game.over:
                break
            probability = risks(game.visible())
            certain = [x for x, p in probability.items() if p == 0]
            assert all(not game.mines[x] for x in certain)
            game.click(teacher_move(game.visible()))


def test_saved_moves_replay_exactly():
    game = Game(6)
    while not game.over:
        game.click(teacher_move(game.visible()))
    restored, states = replay(6, game.record()["moves"])
    assert restored.record() == game.record()
    assert len(states) == len(game.moves)


def test_showcase_mine_count_round_trips():
    game = Game(7273, n_mines=5, opening_radius=0)
    assert int(game.mines.sum()) == 5
    while not game.over:
        game.click(teacher_move(game.visible()))
    restored, _ = replay(7273, game.record()["moves"], n_mines=5, opening_radius=0)
    assert restored.record() == game.record()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
