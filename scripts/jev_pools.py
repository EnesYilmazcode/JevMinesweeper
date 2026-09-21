"""Run Jev over every rung of the race ladder. usage: jev_pools.py [mines per stage] [parallel]

Seeds are tied to the mine count so the fly and Jev pools line up, which is what lets the last
stage put both players on one shared minefield.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LADDER = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [6, 7, 8, 9, 10]
PARALLEL = sys.argv[2] if len(sys.argv) > 2 else "6"
SIZE = {6: 300, 7: 300, 8: 300, 9: 400, 10: 500}


def seeds(mines):
    first = 80000 + mines * 1000
    return first, first + SIZE.get(mines, 300)


for mines in LADDER:
    first, last = seeds(mines)
    done = {int(p.stem) for p in (ROOT / "runs" / f"jev-{mines}-r0").glob("*.json")}
    start = first
    while start < last and start in done:
        start += 1
    if start >= last:
        print(f"{mines} mines: already have {len(done)} games", flush=True)
        continue
    print(f"=== {mines} mines: seeds {start}-{last} ===", flush=True)
    for attempt in range(3):
        done = subprocess.run([sys.executable, "-X", "utf8", "-u", str(ROOT / "scripts" / "jev_games.py"),
                               str(start), str(last), PARALLEL, str(mines), "0"], cwd=ROOT)
        if done.returncode == 0:
            break
        have = {int(p.stem) for p in (ROOT / "runs" / f"jev-{mines}-r0").glob("*.json")}
        missing = sorted(set(range(start, last)) - have)
        if not missing:
            break
        print(f"retrying {len(missing)} unfinished seeds at {mines} mines", flush=True)
        start = missing[0]

print("\n=== pool summary ===", flush=True)
import json
for mines in LADDER:
    games = [json.loads(p.read_text(encoding="utf8"))
             for p in (ROOT / "runs" / f"jev-{mines}-r0").glob("*.json")]
    clears = [g for g in games if g["won"]]
    best = max((len(g["moves"]) for g in clears), default=0)
    print(f"{mines:2d} mines: {len(clears):3d} clears in {len(games):4d} games "
          f"({len(clears) / max(1, len(games)):.1%}), longest clear {best} clicks", flush=True)
