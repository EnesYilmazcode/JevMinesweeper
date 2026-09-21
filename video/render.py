"""Render verified Fly vs Jev Minesweeper replays with animation and sound.

usage: python video/render.py <seed> [out.mp4] [fps]
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from minesweeper.game import COLS, COVERED, MINE, N_MINES, ROWS, replay
from sound import mix, write_wav

W, H, SS = 1400, 850, 2
BG, GRID, COVER = "#faf8ef", "#d6cec2", "#aaa196"
REVEALED, TEXT, MUTED, ACCENT, DANGER = "#eee4da", "#776e65", "#9b9187", "#2f9e75", "#f05f50"
NUMBER = {1: "#2563eb", 2: "#16a34a", 3: "#dc2626", 4: "#6d28d9", 5: "#9f1239", 6: "#0891b2", 7: "#111827", 8: "#64748b"}
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
BOARD = 560
CELL = BOARD / 9
ORIGIN = {"fly": (100, 180), "jev": (740, 180)}
INTRO, OUTRO = 0.55, 1.65


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, int(size * SS))


def schedule(count):
    return np.maximum(0.085, 0.40 * 0.91 ** np.arange(count))


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle([x * SS for x in box], radius=radius * SS, fill=fill, outline=outline, width=width * SS)


def center_text(draw, xy, value, fnt, fill):
    draw.text((xy[0] * SS, xy[1] * SS), value, font=fnt, fill=fill, anchor="mm")


def cell_box(player, r, c, inset=3):
    x, y = ORIGIN[player]
    return (x + c * CELL + inset, y + r * CELL + inset, x + (c + 1) * CELL - inset, y + (r + 1) * CELL - inset)


def draw_mine(draw, player, r, c, exploded=False):
    x1, y1, x2, y2 = cell_box(player, r, c, 14)
    color = DANGER if exploded else "#172033"
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    radius = 13
    for angle in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        inner = (cx + np.cos(angle) * radius * 0.75, cy + np.sin(angle) * radius * 0.75)
        outer = (cx + np.cos(angle) * radius * 1.45, cy + np.sin(angle) * radius * 1.45)
        draw.line((inner[0] * SS, inner[1] * SS, outer[0] * SS, outer[1] * SS), fill=color, width=4 * SS)
    draw.ellipse(((cx - radius) * SS, (cy - radius) * SS, (cx + radius) * SS, (cy + radius) * SS), fill=color)
    draw.ellipse(((cx - 5) * SS, (cy - 7) * SS, (cx + 1) * SS, (cy - 1) * SS), fill="#ffffff")


def draw_flag(draw, player, r, c):
    x1, y1, x2, y2 = cell_box(player, r, c, 10)
    pole_x, top, bottom = x1 + (x2 - x1) * 0.40, y1 + 4, y2 - 5
    draw.line((pole_x * SS, top * SS, pole_x * SS, bottom * SS), fill="#f9f6f2", width=4 * SS)
    draw.polygon(((pole_x * SS, top * SS), ((x2 - 3) * SS, (top + 9) * SS), (pole_x * SS, (top + 19) * SS)), fill=DANGER)
    draw.line(((pole_x - 8) * SS, bottom * SS, (pole_x + 9) * SS, bottom * SS), fill="#f9f6f2", width=4 * SS)


def draw_board(draw, player, state, previous, progress, game, flags):
    board = state["visible"]
    opened_list = [tuple(x) for x in state["opened"]]
    opened = set(opened_list)
    lost = state["exploded"] is not None
    reveal_order = {cell: i for i, cell in enumerate(opened_list)}
    for r in range(ROWS):
        for c in range(COLS):
            value = int(board[r, c])
            box = cell_box(player, r, c)
            if value == COVERED:
                rounded(draw, box, 7, COVER)
                if (r, c) in flags:
                    draw_flag(draw, player, r, c)
            else:
                if (r, c) in opened:
                    delay = 0.42 * reveal_order[(r, c)] / max(1, len(opened_list) - 1)
                    local = np.clip((progress - delay) / max(0.01, 1 - delay), 0, 1)
                    scale = 0.18 + 0.82 * (1 - (1 - local) ** 3)
                else:
                    scale = 1
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                half = CELL * 0.46 * scale
                rounded(draw, (cx - half, cy - half, cx + half, cy + half), 7, REVEALED, outline="#d9cfc2", width=1)
                if value > 0:
                    center_text(draw, (cx, cy), str(value), font(35, True), NUMBER[value])
                elif value == MINE:
                    draw_mine(draw, player, r, c, True)
    if lost and progress > 0.5:
        for r, c in np.argwhere(game.mines):
            if (int(r), int(c)) != tuple(state["exploded"]):
                draw_mine(draw, player, int(r), int(c))
    clicked = tuple(state["clicked"])
    x1, y1, x2, y2 = cell_box(player, *clicked, 2)
    draw.rounded_rectangle([x1 * SS, y1 * SS, x2 * SS, y2 * SS], radius=8 * SS, outline=ACCENT, width=3 * SS)


def draw_status(draw, player, game, state, label):
    x, y = ORIGIN[player]
    draw.text((x * SS, 115 * SS), label, font=font(72, True), fill=TEXT, anchor="lm")
    safe = int(np.sum(state["visible"] >= 0))
    bw, bh = 180, 92
    bx, by = x + BOARD - bw, 69
    rounded(draw, (bx, by, bx + bw, by + bh), 8, "#bbada0")
    center_text(draw, (bx + bw / 2, by + 24), "SAFE", font(18, True), "#eee4da")
    center_text(draw, (bx + bw / 2, by + 60), f"{safe} / {ROWS * COLS - game.n_mines}", font(31, True), "#ffffff")


def draw_finish(image, player, state, game, alpha):
    if not (state["exploded"] is not None or state["won"]) or alpha <= 0:
        return
    x, y = ORIGIN[player]
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    tint = (237, 207, 114) if state["won"] else (238, 228, 218)
    draw.rounded_rectangle((x * SS, y * SS, (x + BOARD) * SS, (y + BOARD) * SS), radius=10 * SS,
                           fill=(*tint, int(210 * alpha)))
    title = "Cleared!" if state["won"] else "Game over"
    center_text(draw, (x + BOARD / 2, y + BOARD / 2 - 22), title, font(59, True),
                (119, 110, 101, int(255 * alpha)))
    safe = int(np.sum(state["visible"] >= 0))
    center_text(draw, (x + BOARD / 2, y + BOARD / 2 + 45), f"{safe} / {81 - game.n_mines} safe", font(27, True),
                (119, 110, 101, int(225 * alpha)))
    image.alpha_composite(overlay)


def frame_at(games, states, beliefs, starts, durs, time):
    image = Image.new("RGBA", (W * SS, H * SS), BG)
    draw = ImageDraw.Draw(image)
    for player, label in (("fly", "Fly"), ("jev", "Jev")):
        player_states = states[player]
        k = int(np.searchsorted(starts, time, side="right") - 1)
        k = max(0, min(k, len(player_states) - 1))
        progress = 1 if k == 0 or k >= len(durs) else np.clip((time - starts[k]) / durs[k], 0, 1)
        state = player_states[k]
        draw_status(draw, player, games[player], state, label)
        flags = {tuple(x) for x in beliefs[player][min(k, len(beliefs[player]) - 1)]} if beliefs[player] else set()
        draw_board(draw, player, state, player_states[max(0, k - 1)], progress, games[player], flags)
        draw_finish(image, player, state, games[player], np.clip((progress - 0.42) / 0.35, 0, 1))
    center_text(draw, (W / 2, 803), f"SAME {games['fly'].n_mines}-MINE BOARD  ·  VISIBLE CLUES ONLY", font(22, True), MUTED)
    return image.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)


def main():
    seed = int(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "renders" / f"fly-vs-jev-{seed}.mp4"
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    n_mines = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    games, states, beliefs = {}, {}, {}
    suffix = "" if n_mines == 10 else f"-{n_mines}"
    for player, folder in (("fly", f"fly-none{suffix}"), ("jev", f"jev{suffix}")):
        path = ROOT / "runs" / folder / f"{seed}.json"
        if not path.exists() and n_mines != 10:
            path = ROOT / "results" / "showcase" / f"{player}.json"
        record = json.loads(path.read_text(encoding="utf8"))
        games[player], states[player] = replay(seed, record["moves"], n_mines=record.get("n_mines", n_mines))
        beliefs[player] = record.get("flags", [])
    longest = max(len(x) for x in states.values())
    durs = schedule(longest)
    starts = INTRO + np.concatenate(([0], np.cumsum(durs[:-1])))
    total = starts[-1] + durs[-1] + OUTRO
    out.parent.mkdir(parents=True, exist_ok=True)
    silent = out.with_suffix(".silent.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "slow",
                           "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(silent)], stdin=subprocess.PIPE)
    frames = int(total * fps)
    for i in range(frames):
        ff.stdin.write(frame_at(games, states, beliefs, starts, durs, i / fps).tobytes())
        if i % 300 == 0: print(f"frame {i}/{frames}", flush=True)
    ff.stdin.close(); ff.wait()
    if ff.returncode: raise RuntimeError(f"ffmpeg exited {ff.returncode}")
    events = []
    for player in ("fly", "jev"):
        pan = -0.58 if player == "fly" else 0.58
        for k, state in enumerate(states[player][1:], 1):
            if k >= len(starts): break
            events.append((starts[k], "click", pan, 0))
            if state["exploded"] is not None: events.append((starts[k] + 0.08, "boom", pan, 0))
            elif state["won"]: events.append((starts[k] + 0.08, "win", pan, 0))
            elif len(state["opened"]) > 1: events.append((starts[k] + 0.07, "reveal", pan, len(state["opened"])))
    wav = out.with_suffix(".wav")
    write_wav(wav, mix(events, total))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    silent.unlink(); wav.unlink()
    print(f"wrote {out}: {total:.1f}s, fly {'won' if games['fly'].won else 'lost'}, Jev {'won' if games['jev'].won else 'lost'}")


if __name__ == "__main__":
    main()
