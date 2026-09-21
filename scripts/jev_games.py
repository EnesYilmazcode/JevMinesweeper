"""Run Jev on seeded Minesweeper boards. usage: first last [parallel games]"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from minesweeper.game import Game
from minesweeper.jev import jev_move

OUT = ROOT / "runs" / "jev"
OUT.mkdir(parents=True, exist_ok=True)


def one(seed):
    game, tokens, confidence, started = Game(seed), 0, [], time.time()
    while not game.over:
        move, p, used = jev_move(game.visible(), game.legal_cells())
        game.click(move); confidence.append(p); tokens += used
    record = {**game.record(), "confidence": confidence, "tokens": tokens, "seconds": round(time.time() - started)}
    (OUT / f"{seed}.json").write_text(json.dumps(record), encoding="utf8")
    print(f"seed {seed}: {'WIN' if game.won else 'mine'}, {game.safe_revealed}/71 safe, {tokens} tokens", flush=True)
    return record


if __name__ == "__main__":
    first, last = int(sys.argv[1]), int(sys.argv[2])
    with ThreadPoolExecutor(int(sys.argv[3]) if len(sys.argv) > 3 else 4) as pool:
        list(pool.map(one, range(first, last)))

