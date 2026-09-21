"""Run visible-information teacher and random baselines."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from minesweeper.game import Game
from minesweeper.solver import teacher_move

first, last = int(sys.argv[1]), int(sys.argv[2])
for mode in ("solver", "random"):
    out = ROOT / "runs" / mode
    out.mkdir(parents=True, exist_ok=True)
    for seed in range(first, last):
        game, rng = Game(seed), np.random.default_rng(seed + 991)
        while not game.over:
            cell = teacher_move(game.visible()) if mode == "solver" else game.legal_cells()[int(rng.integers(len(game.legal_cells())))]
            game.click(cell)
        (out / f"{seed}.json").write_text(json.dumps(game.record()), encoding="utf8")

