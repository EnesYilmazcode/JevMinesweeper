"""MaleCNS leaky integrate-and-fire model shared with Flytris and Fly2048."""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch

DATA = Path(os.environ.get("FLYTRIS_DATA", Path(__file__).resolve().parents[2] / "Flytris" / "data" / "malecns"))
V0, V_RST, V_TH = -52.0, -52.0, -45.0
T_MBR, TAU_SYN, W_SYN, F_POI = 20.0, 5.0, 0.275, 250
DELAY_STEPS, REFRACTORY_STEPS, DT = 2, 2, 1.0


def load_neurons(columns=None):
    return pd.read_parquet(DATA / "neurons.parquet", columns=columns)


def load_edges(threshold):
    z = np.load(DATA / "edges.npz")
    keep = np.nonzero(z["syn"] >= threshold)[0]
    return {k: z[k][keep] for k in ("pre", "post", "sign", "syn")}


class Brain:
    def __init__(self, threshold=5, device="cuda"):
        self.device = device
        neurons = load_neurons(["idx", "type"])
        self.n = len(neurons)
        e = load_edges(threshold)
        sign = e["sign"].astype(np.float32)
        sensory = neurons.type.str.match(r"^R[1-8]", na=False).to_numpy()
        sign[sensory[e["pre"]]] = 1.0
        weights = e["syn"].astype(np.float32) * sign * W_SYN
        order = np.lexsort((e["pre"], e["post"]))
        post, pre, weights = e["post"][order], e["pre"][order], weights[order]
        crow = np.zeros(self.n + 1, np.int64)
        np.cumsum(np.bincount(post, minlength=self.n), out=crow[1:])
        self.W = torch.sparse_csr_tensor(torch.from_numpy(crow), torch.from_numpy(pre.astype(np.int64)),
                                         torch.from_numpy(weights), (self.n, self.n)).to(device)
        self.k_v, self.a_g = 1 - np.exp(-DT / T_MBR), float(np.exp(-DT / TAU_SYN))

    @torch.no_grad()
    def run(self, in_idx, p_in, steps, record_idx, phase):
        batch, dev = p_in.shape[1], self.device
        v = torch.full((self.n, batch), V0, device=dev)
        g = torch.zeros((self.n, batch), device=dev)
        refractory = torch.zeros((self.n, batch), dtype=torch.int8, device=dev)
        delay = [torch.zeros((self.n, batch), device=dev) for _ in range(DELAY_STEPS)]
        counts = torch.zeros((len(record_idx), batch), device=dev)
        accumulator = phase[:, None].expand(-1, batch).clone()
        for t in range(steps):
            g.mul_(self.a_g).add_(torch.sparse.mm(self.W, delay[t % DELAY_STEPS]))
            v.mul_(1 - self.k_v).add_(g, alpha=self.k_v).add_(V0 * self.k_v)
            v.masked_fill_(refractory > 0, V_RST)
            accumulator.add_(p_in)
            fire = (accumulator >= 1).float()
            accumulator.sub_(fire)
            v.index_add_(0, in_idx, fire * (F_POI * W_SYN))
            spikes = v > V_TH
            v.masked_fill_(spikes, V_RST)
            g.masked_fill_(spikes, 0)
            refractory = torch.where(spikes, REFRACTORY_STEPS, (refractory - 1).clamp_(min=0)).to(torch.int8)
            delay[t % DELAY_STEPS] = spikes.float()
            counts += delay[t % DELAY_STEPS][record_idx]
        return counts

