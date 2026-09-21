import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "results" / "games"
out.mkdir(parents=True, exist_ok=True)
for folder in ("fly-none", "jev", "solver", "random", "fly-shuffled_input", "fly-shuffled_readout", "fly-silenced"):
    games = {}
    for path in sorted((ROOT / "runs" / folder).glob("*.json"), key=lambda p: int(p.stem)):
        record = json.loads(path.read_text(encoding="utf8"))
        games[path.stem] = {k: record[k] for k in ("won", "safe_revealed", "n_clicks", "moves")}
    (out / f"{folder}.json").write_text(json.dumps(games), encoding="utf8")
    print(folder, len(games))
for name in ("readout.npz", "gate.json"):
    shutil.copy(ROOT / "runs" / "readout" / name, ROOT / "results" / name)
