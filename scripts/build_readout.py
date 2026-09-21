"""Train a linear readout on MaleCNS activity elicited by candidate Minesweeper clicks."""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from minesweeper.brain import Brain, load_neurons
from minesweeper.eyes import Eyes, encode
from minesweeper.game import Game
from minesweeper.solver import action_values, teacher_move

N_POSITIONS = int(sys.argv[1]) if len(sys.argv) > 1 else 500
KEEP = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
STEPS, BATCH = 150, 256
OUT = Path(os.environ.get("MINESWEEPER_RUNS", ROOT / "runs")) / "readout"
OUT.mkdir(parents=True, exist_ok=True)


def collect_positions():
    cache = OUT / "positions.npz"
    if cache.exists():
        with np.load(cache) as z:
            return {k: z[k] for k in z.files}
    boards, rows, cols, targets, groups, games = [], [], [], [], [], []
    seed, group = 100_000, 0
    while group < N_POSITIONS:
        game = Game(seed)
        while not game.over and group < N_POSITIONS:
            board = game.visible()
            values = action_values(board)
            cells, raw = list(values), np.asarray(list(values.values()), np.float32)
            # Balance the safest-looking and most dangerous candidates so the readout sees contrast.
            ranked = np.argsort(-raw, kind="stable")
            order = np.unique(np.concatenate((ranked[:min(12, len(ranked))], ranked[-min(12, len(ranked)):])))
            selected = [cells[i] for i in order]
            y = raw[order]
            y = (y - y.mean()) / max(float(y.std()), 1e-6)
            for cell, target in zip(selected, y):
                boards.append(board)
                rows.append(cell[0]); cols.append(cell[1]); targets.append(target)
                groups.append(group); games.append(seed)
            group += 1
            game.click(teacher_move(board))
        print(f"teacher seed {seed}: {'won' if game.won else 'lost'}, {game.safe_revealed} safe, {group}/{N_POSITIONS}", flush=True)
        seed += 1
    data = {"boards": np.asarray(boards, np.int8), "rows": np.asarray(rows, np.int8),
            "cols": np.asarray(cols, np.int8), "target": np.asarray(targets, np.float32),
            "group": np.asarray(groups, np.int32), "game": np.asarray(games, np.int32)}
    np.savez(cache, **data)
    return data


def simulate(data):
    cache = OUT / "spikes.npz"
    if cache.exists():
        with np.load(cache) as z:
            return z["counts"].astype(np.float32), z["neurons"]
    brain, eyes = Brain(), Eyes()
    neurons = load_neurons(["idx", "type"])
    rec_np = neurons.loc[neurons.type.isin(["L1", "L2"]), "idx"].sort_values().to_numpy(np.int64)
    rec = torch.as_tensor(rec_np, device="cuda")
    counts = np.empty((len(data["target"]), len(rec_np)), np.float16)
    started = time.time()
    for start in range(0, len(counts), BATCH):
        stop = min(start + BATCH, len(counts))
        # Each cached sample may have a different board; group same-board candidates into calls.
        pieces = []
        for i in range(start, stop):
            cell = [(int(data["rows"][i]), int(data["cols"][i]))]
            pieces.append(eyes.probs(data["boards"][i], cell))
        probs = torch.cat(pieces, dim=1)
        counts[start:stop] = brain.run(eyes.in_idx, probs, STEPS, rec, eyes.phase).T.cpu().numpy()
        print(f"simulated {stop}/{len(counts)} candidates, {time.time() - started:.0f}s", flush=True)
    np.savez(cache, counts=counts, neurons=rec_np)
    return counts.astype(np.float32), rec_np


def centered(x, group):
    sums = np.zeros((group.max() + 1, x.shape[1]), np.float64)
    np.add.at(sums, group, x)
    return x - (sums / np.bincount(group)[:, None])[group]


def fit(x, y, group, train, label):
    xc = centered(x.astype(np.float64), group)
    scale = xc[train].std(0); scale[scale < 1e-6] = 1
    z = xc / scale
    test_groups = np.unique(group[~train])
    best = None
    for lam in (0.1, 1, 10, 100, 1000):
        xt = z[train]
        weights = np.linalg.solve(xt.T @ xt + lam * np.eye(z.shape[1]), xt.T @ y[train])
        scores = z @ weights
        accuracy = np.mean([y[group == g][np.argmax(scores[group == g])] >= y[group == g].max() - 0.05 for g in test_groups])
        print(f"{label}: lambda {lam:g}, held-out best-click agreement {accuracy:.3f}", flush=True)
        if best is None or accuracy > best[0]:
            best = accuracy, lam, weights, scale
    return best


def main():
    data = collect_positions()
    counts, neurons = simulate(data)
    group, y = data["group"].astype(np.int64), data["target"]
    game_ids = np.unique(data["game"])
    test_games = game_ids[-max(2, len(game_ids) // 5):]
    train = ~np.isin(data["game"], test_games)
    xc = centered(counts.astype(np.float64), group)
    cov = ((xc[train] - xc[train].mean(0)) * y[train, None]).sum(0)
    selected = np.argsort(-np.abs(cov), kind="stable")[:KEEP]
    fly = fit(counts[:, selected], y, group, train, f"fly, {KEEP} L1/L2 neurons")
    direct = np.vstack([encode(b, [(int(r), int(c))])[0] for b, r, c in zip(data["boards"], data["rows"], data["cols"])])
    no_brain = fit(direct, y, group, train, "no brain, 162 eye channels")
    np.savez(OUT / "readout.npz", neuron_idx=neurons[selected], scale=fly[3], weights=fly[2], steps=STEPS,
             heldout_agreement=fly[0], ridge_lambda=fly[1])
    report = {"positions": int(group.max() + 1), "candidates": len(y), "teacher_games": len(game_ids),
              "test_games": [int(x) for x in test_games], "fly_agreement": float(fly[0]),
              "chance_agreement": float(np.mean([1 / np.sum(group == g) for g in np.unique(group[~train])])),
              "no_brain_agreement": float(no_brain[0]), "neurons_kept": KEEP,
              "mean_l1l2_spikes": float(counts.mean())}
    (OUT / "gate.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
