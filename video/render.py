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

W, H, SS = 1800, 1200, 2
BG, PANEL, GRID, COVER = "#0b1220", "#111c30", "#263855", "#31527d"
REVEALED, TEXT, MUTED, ACCENT, DANGER = "#e8eef7", "#f8fafc", "#9fb0c8", "#65d6ad", "#ff6b6b"
NUMBER = {1: "#2563eb", 2: "#16a34a", 3: "#dc2626", 4: "#6d28d9", 5: "#9f1239", 6: "#0891b2", 7: "#111827", 8: "#64748b"}
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
BOARD = 650
CELL = BOARD / 9
ORIGIN = {"fly": (155, 375), "jev": (995, 375)}
INTRO, OUTRO = 1.1, 2.6


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, int(size * SS))


def schedule(count):
    return np.maximum(0.17, 0.72 * 0.945 ** np.arange(count))


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


def draw_board(draw, player, state, previous, progress, game):
    board = state["visible"]
    opened = {tuple(x) for x in state["opened"]}
    lost = state["exploded"] is not None
    for r in range(ROWS):
        for c in range(COLS):
            value = int(board[r, c])
            box = cell_box(player, r, c)
            if value == COVERED:
                rounded(draw, box, 7, COVER)
            else:
                scale = (0.35 + 0.65 * min(1, progress * 1.5)) if (r, c) in opened else 1
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                half = CELL * 0.46 * scale
                rounded(draw, (cx - half, cy - half, cx + half, cy + half), 7, REVEALED)
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


def draw_status(draw, player, game, state, label, subtitle):
    x, y = ORIGIN[player]
    draw.text((x * SS, 218 * SS), label, font=font(76, True), fill=TEXT)
    draw.text((x * SS, 308 * SS), subtitle, font=font(25), fill=MUTED)
    safe = int(np.sum(state["visible"] >= 0))
    status = "CLEARED" if state["won"] else (f"MINE · {safe}/{ROWS * COLS - N_MINES} SAFE" if state["exploded"] is not None else f"{safe} / {ROWS * COLS - N_MINES} SAFE")
    color = ACCENT if state["won"] else (DANGER if state["exploded"] is not None else TEXT)
    draw.text(((x + BOARD) * SS, 258 * SS), status, font=font(31, True), fill=color, anchor="ra")


def frame_at(games, states, starts, durs, time):
    image = Image.new("RGB", (W * SS, H * SS), BG)
    draw = ImageDraw.Draw(image)
    center_text(draw, (W / 2, 72), "WHO PLAYS MINESWEEPER BETTER?", font(28, True), ACCENT)
    center_text(draw, (W / 2, 133), "166,700 fly neurons  vs  Jev", font(48, True), TEXT)
    draw.line((W / 2 * SS, 212 * SS, W / 2 * SS, 1055 * SS), fill=GRID, width=2 * SS)
    for player, label, subtitle in (("fly", "Fly", "MaleCNS connectome + learned readout"),
                                    ("jev", "Jev", "same board · visible clues only")):
        player_states = states[player]
        k = int(np.searchsorted(starts, time, side="right") - 1)
        k = max(0, min(k, len(player_states) - 1))
        progress = 1 if k >= len(durs) else np.clip((time - starts[k]) / durs[k], 0, 1)
        state = player_states[k]
        draw_status(draw, player, games[player], state, label, subtitle)
        draw_board(draw, player, state, player_states[max(0, k - 1)], progress, games[player])
    center_text(draw, (W / 2, 1110), "Identical seeded minefield  ·  guaranteed-safe center opening", font(25), MUTED)
    return image.resize((W, H), Image.Resampling.LANCZOS)


def main():
    seed = int(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "renders" / f"fly-vs-jev-{seed}.mp4"
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    games, states = {}, {}
    for player, folder in (("fly", "fly-none"), ("jev", "jev")):
        record = json.loads((ROOT / "runs" / folder / f"{seed}.json").read_text(encoding="utf8"))
        games[player], states[player] = replay(seed, record["moves"])
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
        ff.stdin.write(frame_at(games, states, starts, durs, i / fps).tobytes())
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
