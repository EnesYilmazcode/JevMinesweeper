"""Visible board plus candidate click -> spike rates in the fly's photoreceptors."""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from .game import COLS, COVERED, ROWS

DATA = Path(os.environ.get("FLYTRIS_DATA", Path(__file__).resolve().parents[2] / "Flytris" / "data" / "malecns"))
MAP = Path(os.environ.get("MINESWEEPER_EYE_MAP", DATA / "eye_map_minesweeper.npz"))
N_CELLS = ROWS * COLS
PHASE_SEED = 20260920


def encode(board, candidates):
    """Left eye sees the board; right eye sees the same clues centered on the proposed click."""
    state2d = np.where(board == COVERED, 0.04, 0.22 + np.maximum(board, 0) * 0.095).astype(np.float32)
    out = np.zeros((len(candidates), N_CELLS * 2), np.float32)
    out[:, :N_CELLS] = state2d.reshape(-1)
    for i, (r, c) in enumerate(candidates):
        relative = np.zeros((ROWS, COLS), np.float32)
        for rr in range(ROWS):
            for cc in range(COLS):
                source = (r + rr - ROWS // 2, c + cc - COLS // 2)
                if 0 <= source[0] < ROWS and 0 <= source[1] < COLS:
                    relative[rr, cc] = state2d[source]
        relative[ROWS // 2, COLS // 2] = 1.0
        out[i, N_CELLS:] = relative.reshape(-1)
    return out


def build_eye_map():
    neurons = pd.read_parquet(DATA / "neurons.parquet", columns=["idx", "body_id", "type", "side"])
    receptors = neurons[neurons.type == "R1-R6"]
    indexes, channels, scales, counts = [], [], [], {}
    for eye, side in enumerate("LR"):
        cells = receptors[receptors.side == side].sort_values("body_id")
        counts[side] = len(cells)
        indexes.append(cells.idx.to_numpy(np.int64))
        channels.append(eye * N_CELLS + np.minimum(np.arange(len(cells)) * N_CELLS // len(cells), N_CELLS - 1))
    biggest = max(counts.values())
    for side in "LR":
        scales.append(np.full(counts[side], biggest / counts[side], np.float32))
    MAP.parent.mkdir(parents=True, exist_ok=True)
    np.savez(MAP, in_idx=np.concatenate(indexes), channel=np.concatenate(channels), scale=np.concatenate(scales))
    return np.load(MAP)


class Eyes:
    def __init__(self, board_hz=500.0, device="cuda"):
        m = np.load(MAP) if MAP.exists() else build_eye_map()
        self.in_idx = torch.from_numpy(m["in_idx"]).to(device)
        self.channel = torch.from_numpy(m["channel"]).to(device)
        self.scale = torch.from_numpy(m["scale"]).to(device)
        self.phase = torch.from_numpy(np.random.default_rng(PHASE_SEED).random(len(m["in_idx"]), dtype=np.float32)).to(device)
        self.board_hz, self.device = board_hz, device

    def probs(self, board, candidates):
        values = torch.as_tensor(encode(board, candidates).T, device=self.device)
        return (values[self.channel] * self.scale[:, None] * self.board_hz * 1e-3).clamp_(0, 1)
