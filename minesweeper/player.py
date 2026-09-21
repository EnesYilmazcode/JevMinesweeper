"""Connectome-backed Minesweeper player."""
import numpy as np
import torch

from .brain import Brain
from .eyes import Eyes


class FlyPlayer:
    def __init__(self, readout_file, control="none", device="cuda", max_batch=256):
        with np.load(readout_file) as z:
            self.rec = torch.as_tensor(z["neuron_idx"].astype(np.int64), device=device)
            self.scale, self.weights = z["scale"].astype(np.float32), z["weights"].astype(np.float32)
            self.steps = int(z["steps"])
        self.brain, self.eyes, self.max_batch = Brain(device=device), Eyes(device=device), max_batch
        rng = np.random.default_rng(20260920)
        if control == "silenced":
            self.weights[:] = 0
        elif control == "shuffled_readout":
            self.weights = self.weights[rng.permutation(len(self.weights))]
        elif control == "shuffled_input":
            perm = torch.as_tensor(rng.permutation(len(self.eyes.in_idx)), device=device)
            self.eyes.in_idx = self.eyes.in_idx[perm]
        elif control != "none":
            raise ValueError(control)

    def scores(self, board, candidates):
        out = np.empty(len(candidates), np.float32)
        for start in range(0, len(candidates), self.max_batch):
            chunk = candidates[start:start + self.max_batch]
            counts = self.brain.run(self.eyes.in_idx, self.eyes.probs(board, chunk), self.steps, self.rec, self.eyes.phase)
            out[start:start + len(chunk)] = (counts.T.cpu().numpy() / self.scale) @ self.weights
        return out

