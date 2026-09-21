"""Print a Markdown benchmark table from recorded games."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
first, last = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (6000, 6016)
players = [("fly-none", "Fly (connectome + readout)"), ("jev", "Jev"), ("solver", "Constraint solver"),
           ("random", "Random clicks"), ("fly-shuffled_input", "Fly, eye wiring shuffled"),
           ("fly-shuffled_readout", "Fly, readout shuffled"), ("fly-silenced", "Fly, readout silenced")]
print("| Player | Games | Wins | Win rate | Mean safe squares | Median |")
print("|---|---:|---:|---:|---:|---:|")
for folder, name in players:
    games = []
    for seed in range(first, last):
        path = ROOT / "runs" / folder / f"{seed}.json"
        if path.exists(): games.append(json.loads(path.read_text(encoding="utf8")))
    if games:
        safe = np.asarray([g["safe_revealed"] for g in games])
        wins = sum(g["won"] for g in games)
        print(f"| {name} | {len(games)} | {wins} | {wins / len(games):.1%} | {safe.mean():.1f} / 71 | {np.median(safe):.0f} |")

