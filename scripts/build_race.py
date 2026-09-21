"""Pick the showcase race stages from the saved pools. usage: build_race.py [mines per stage]

Each stage is one rung of a mine ladder, so the boards get denser as the race goes on and a
single click stops clearing half the grid. Every stage but the last is a clear for both lanes.
The last rung is run on one shared minefield so the finish is a genuine head to head.
"""
import json
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from minesweeper.game import Game

RUNS = ROOT / "runs"
LADDER = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [6, 7, 8, 9, 10]
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "results" / "showcase" / "race.json"
RADIUS = 0
# Boards whose centre opening cascades give most of the grid away before either player moves.
# Openings are all-or-nothing at these densities, so capping at one clue costs nothing but choice.
OPENING_CAP = 1
# Jev's last board should end while the fly is still working, as a share of the fly's clicks.
FINISH_GAP = 0.55


def pool(player, mines):
    folder = RUNS / (f"fly-none-{mines}-r{RADIUS}" if player == "fly" else f"jev-{mines}-r{RADIUS}")
    games = {}
    for path in folder.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf8"))
        record["seed"] = int(path.stem)
        record["opening"] = Game(record["seed"], n_mines=mines, opening_radius=RADIUS).safe_revealed
        games[record["seed"]] = record
    if not games:
        raise SystemExit(f"no games in {folder}; run the pool for {mines} mines first")
    return games


def usable(games, won):
    return {s: g for s, g in games.items() if g["won"] == won and g["opening"] <= OPENING_CAP}


def stage_entry(record):
    return {"seed": record["seed"], "won": bool(record["won"]),
            "moves": record["moves"], "flags": record["flags"]}


def rising(options):
    """One clear per rung, never fewer clicks than the rung before, as many clicks as possible.

    Clears are rare at the top of the ladder, so the longest clear at each rung on its own can
    zigzag. Choosing the whole sequence at once keeps the race building.
    """
    from functools import lru_cache

    @lru_cache(None)
    def best(rung, floor):
        if rung == len(options):
            return 0, ()
        allowed = [x for x in options[rung] if x[0] >= floor] or list(options[rung])
        picks = []
        for clicks, seed in allowed:
            total, rest = best(rung + 1, clicks)
            picks.append((clicks + total, ((clicks, seed),) + rest))
        return max(picks)

    return [seed for _, seed in best(0, 0)[1]]


def main():
    pools = {(p, m): pool(p, m) for m in LADDER for p in ("fly", "jev")}
    climb, top = LADDER[:-1], LADDER[-1]
    notes = {m: "independent boards" for m in LADDER}

    # The top rung is the one stage Jev does not survive. Prefer a single shared minefield so the
    # finish is head to head; fall back to independent boards rather than give up the opening cap.
    fly_clears, jev_losses = usable(pools[("fly", top)], True), usable(pools[("jev", top)], False)
    shared = [s for s in sorted(set(fly_clears) & set(jev_losses)) if len(jev_losses[s]["moves"]) >= 3]
    if shared:
        seed = max(shared, key=lambda s: (len(fly_clears[s]["moves"]), len(jev_losses[s]["moves"])))
        final = {"fly": fly_clears[seed], "jev": jev_losses[seed]}
        notes[top] = f"shared minefield, seed {seed}"
    else:
        if not fly_clears or not jev_losses:
            raise SystemExit(f"no usable {top}-mine finish: {len(fly_clears)} fly clears, "
                             f"{len(jev_losses)} Jev losses under a {OPENING_CAP}-clue opening")
        fly_final = max(fly_clears.values(), key=lambda g: len(g["moves"]))
        # Losing is what Jev does on almost every board at this density, so the choice is only
        # about pacing: take the loss that got furthest among those that end while the fly is
        # still playing, so the two lanes visibly finish apart.
        budget = max(3, round(len(fly_final["moves"]) * FINISH_GAP))
        ending_early = [g for g in jev_losses.values() if 3 <= len(g["moves"]) <= budget]
        final = {"fly": fly_final,
                 "jev": max(ending_early or jev_losses.values(),
                            key=lambda g: (g["safe_revealed"], len(g["moves"])))}
        notes[top] = "no shared board survives the opening cap, lanes seeded independently"

    picks = {}
    for player in ("fly", "jev"):
        options = []
        for mines in climb:
            clears = sorted((len(g["moves"]), s) for s, g in usable(pools[(player, mines)], True).items())
            if not clears:
                raise SystemExit(f"no {player} clear at {mines} mines under a {OPENING_CAP}-clue "
                                 f"opening, in {len(pools[(player, mines)])} games")
            options.append(tuple(clears))
        picks[player] = [pools[(player, m)][s] for m, s in zip(climb, rising(tuple(options)))]
        picks[player].append(final[player])

    stages, summary = [], []
    for index, mines in enumerate(LADDER):
        chosen = {p: picks[p][index] for p in ("fly", "jev")}
        stages.append({"n_mines": mines, "opening_radius": RADIUS,
                       "fly": stage_entry(chosen["fly"]), "jev": stage_entry(chosen["jev"])})
        summary.append({"mines": mines, "note": notes[mines],
                        **{f"{p}_pool": len(pools[(p, mines)]) for p in ("fly", "jev")},
                        **{f"{p}_clears": sum(g["won"] for g in pools[(p, mines)].values())
                           for p in ("fly", "jev")},
                        **{f"{p}_clicks": len(chosen[p]["moves"]) for p in ("fly", "jev")},
                        **{f"{p}_opening": chosen[p]["opening"] for p in ("fly", "jev")},
                        **{f"{p}_won": bool(chosen[p]["won"]) for p in ("fly", "jev")}})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"stages": stages, "pools": summary}), encoding="utf8")
    print(f"wrote {OUT}")
    print(f"{'stage':>5s} {'mines':>5s} {'fly clicks':>11s} {'jev clicks':>11s} "
          f"{'fly pool':>16s} {'jev pool':>16s}  note")
    for i, s in enumerate(summary, 1):
        print(f"{i:5d} {s['mines']:5d} {s['fly_clicks']:11d} {s['jev_clicks']:11d} "
              f"{s['fly_clears']:6d}/{s['fly_pool']:<9d} {s['jev_clears']:6d}/{s['jev_pool']:<9d}  {s['note']}")
    print(f"\ntotal clicks on screen: fly {sum(s['fly_clicks'] for s in summary)}, "
          f"jev {sum(s['jev_clicks'] for s in summary)}")


if __name__ == "__main__":
    main()
