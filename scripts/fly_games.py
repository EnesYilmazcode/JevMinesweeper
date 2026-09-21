"""Run connectome-backed Minesweeper games. usage: first last [control]"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from minesweeper.game import Game
from minesweeper.player import FlyPlayer

RUNS = Path(os.environ.get("MINESWEEPER_RUNS", ROOT / "runs"))
first, last = int(sys.argv[1]), int(sys.argv[2])
control = sys.argv[3] if len(sys.argv) > 3 else "none"
out = RUNS / f"fly-{control}"
out.mkdir(parents=True, exist_ok=True)
player = FlyPlayer(RUNS / "readout" / "readout.npz", control=control)
started = time.time()
for seed in range(first, last):
    game = Game(seed)
    while not game.over:
        cells = game.legal_cells()
        scores = player.scores(game.visible(), cells)
        game.click(cells[int(scores.argmax())])
    record = {**game.record(), "control": control}
    (out / f"{seed}.json").write_text(json.dumps(record), encoding="utf8")
    print(f"seed {seed}: {'WIN' if game.won else 'mine'}, {game.safe_revealed}/71 safe, {len(game.moves) - 1} choices", flush=True)
print(f"completed {last - first} games in {time.time() - started:.0f}s", flush=True)

