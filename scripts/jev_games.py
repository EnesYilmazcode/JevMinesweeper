"""Run Jev on seeded Minesweeper boards. usage: first last [parallel games]"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from minesweeper.game import Game
from minesweeper.jev import jev_move, label

N_MINES = int(sys.argv[4]) if len(sys.argv) > 4 else 10
OUT = ROOT / "runs" / ("jev" if N_MINES == 10 else f"jev-{N_MINES}")
OUT.mkdir(parents=True, exist_ok=True)


def one(seed):
    game, tokens, confidence, flags, started = Game(seed, n_mines=N_MINES), 0, [], [], time.time()
    while not game.over:
        cells = game.legal_cells()
        move, p, used, probabilities = jev_move(game.visible(), cells, n_mines=N_MINES)
        by_label = {label(x): x for x in cells}
        ranked = sorted(probabilities, key=probabilities.get)
        flags.append([[int(v) for v in by_label[name]] for name in ranked[:min(N_MINES, len(ranked))] if name in by_label])
        game.click(move); confidence.append(p); tokens += used
    record = {**game.record(), "flags": flags, "confidence": confidence, "tokens": tokens, "seconds": round(time.time() - started)}
    (OUT / f"{seed}.json").write_text(json.dumps(record), encoding="utf8")
    print(f"seed {seed}: {'WIN' if game.won else 'mine'}, {game.safe_revealed}/{81 - N_MINES} safe, {tokens} tokens", flush=True)
    return record


if __name__ == "__main__":
    first, last = int(sys.argv[1]), int(sys.argv[2])
    with ThreadPoolExecutor(int(sys.argv[3]) if len(sys.argv) > 3 else 4) as pool:
        list(pool.map(one, range(first, last)))
