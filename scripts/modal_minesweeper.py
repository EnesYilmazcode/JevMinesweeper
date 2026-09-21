"""GPU pipeline on Modal, reusing the Flytris connectome data volume."""
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]
app = modal.App("jev-minesweeper")
data_volume = modal.Volume.from_name("flytris-data")
runs_volume = modal.Volume.from_name("minesweeper-runs-v2", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy==2.4.2", "pandas==2.2.3", "pyarrow==23.0.1", "torch==2.7.1")
         .env({"FLYTRIS_DATA": "/root/data/malecns", "MINESWEEPER_EYE_MAP": "/root/runs/eye_map.npz",
               "MINESWEEPER_RUNS": "/root/runs", "PYTHONUNBUFFERED": "1"})
         .add_local_dir(ROOT / "minesweeper", "/root/minesweeper", ignore=["__pycache__"])
         .add_local_dir(ROOT / "scripts", "/root/scripts", ignore=["__pycache__"]))
job = {"image": image, "gpu": "L4", "cpu": 4, "memory": 16384, "timeout": 3600,
       "volumes": {"/root/data": data_volume, "/root/runs": runs_volume}}


def run(*args):
    import subprocess
    import sys
    try:
        subprocess.run([sys.executable, *args], check=True, cwd="/root")
    finally:
        runs_volume.commit()


@app.function(**job)
def build_readout(positions: int = 500, keep: int = 2048):
    run("/root/scripts/build_readout.py", str(positions), str(keep))


@app.function(**{**job, "timeout": 3 * 3600})
def fly_games(first: int = 6000, last: int = 6016, control: str = "none", mines: int = 10):
    run("/root/scripts/fly_games.py", str(first), str(last), control, str(mines))
