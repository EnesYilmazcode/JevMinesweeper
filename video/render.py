"""Render the verified Fly vs Jev Minesweeper race.

usage: python video/render.py [out.mp4] [fps] [race.json]
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

W, H, SS = 1400, 760, 2
BG, GRID, COVER = "#faf8ef", "#d6cec2", "#aaa196"
REVEALED, TEXT, MUTED, ACCENT, DANGER = "#eee4da", "#776e65", "#9b9187", "#2f9e75", "#f05f50"
NUMBER = {1: "#2563eb", 2: "#16a34a", 3: "#dc2626", 4: "#6d28d9", 5: "#9f1239", 6: "#0891b2", 7: "#111827", 8: "#64748b"}
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_EMOJI = "C:/Windows/Fonts/seguiemj.ttf"
BOARD = 620
CELL = BOARD / ROWS
ORIGIN = {"fly": (55, 112), "jev": (725, 112)}
CURSOR = {"fly": (25, 108, 240), "jev": (229, 81, 186)}
CURSOR_RADIUS, PULSE_RADIUS, CURSOR_HOLD = 23, 48, 0.30
INTRO, OUTRO = 0.55, 1.05
FIRST_READY, NEXT_READY = 0.45, 0.18
CLEAR_HOLD = 0.60
TARGET_SECONDS, MOVE_LIMITS, CASCADE_BONUS = 19.0, (0.15, 0.40), 0.9
# X gives no thumbnail control, so the first frame is the thumbnail: hold the finish, then
# dissolve back to the empty boards and play the race.
LEAD_HOLD, LEAD_FADE = 0.85, 0.45


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, int(size * SS))


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


def cell_center(player, cell):
    x, y = ORIGIN[player]
    return x + (cell[1] + 0.5) * CELL, y + (cell[0] + 0.5) * CELL


def smoothstep(t):
    t = float(np.clip(t, 0, 1))
    return t * t * (3 - 2 * t)


def cursor_at(stage, k, travel, progress):
    """Where the player's pointer is, and how visible it is.

    It rests on the square it just clicked while that reveal plays, then glides to the next
    one and arrives exactly as that click lands.
    """
    clicks = [tuple(state["clicked"]) for state in stage["states"]]
    here = cell_center(stage["player"], clicks[k])
    if k + 1 < len(clicks):
        glide = smoothstep((travel - CURSOR_HOLD) / (1 - CURSOR_HOLD))
        there = cell_center(stage["player"], clicks[k + 1])
        position = (here[0] + (there[0] - here[0]) * glide, here[1] + (there[1] - here[1]) * glide)
    else:
        position = here
    alpha = 1.0
    if k == 0:
        alpha = min(alpha, float(np.clip(travel / 0.25, 0, 1)))
    if k == len(clicks) - 1:
        alpha = min(alpha, 1 - float(np.clip((progress - 0.42) / 0.35, 0, 1)))
    pulse = float(np.clip(travel / 0.28, 0, 1)) if k > 0 else 1.0
    return position, alpha, pulse


def draw_cursor(image, player, position, alpha, pulse):
    if alpha <= 0.01:
        return
    color, pad = CURSOR[player], PULSE_RADIUS + 4
    sprite = Image.new("RGBA", (2 * pad * SS, 2 * pad * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sprite)

    def ring(radius, width, opacity):
        box = ((pad - radius) * SS, (pad - radius) * SS, (pad + radius) * SS, (pad + radius) * SS)
        draw.ellipse(box, outline=(*color, int(255 * opacity)), width=width * SS)

    if pulse < 1:
        ring(CURSOR_RADIUS + (PULSE_RADIUS - CURSOR_RADIUS) * pulse, 3, 0.75 * (1 - pulse) * alpha)
    box = ((pad - CURSOR_RADIUS) * SS, (pad - CURSOR_RADIUS) * SS,
           (pad + CURSOR_RADIUS) * SS, (pad + CURSOR_RADIUS) * SS)
    # A white halo keeps the pointer readable over clue digits in the same colour family.
    draw.ellipse([v + d for v, d in zip(box, (-4 * SS, -4 * SS, 4 * SS, 4 * SS))],
                 outline=(255, 255, 255, int(235 * alpha)), width=4 * SS)
    draw.ellipse(box, fill=(*color, int(64 * alpha)))
    ring(CURSOR_RADIUS, 5, alpha)
    draw.ellipse(((pad - 4) * SS, (pad - 4) * SS, (pad + 4) * SS, (pad + 4) * SS),
                 fill=(*color, int(255 * alpha)))
    image.alpha_composite(sprite, (int((position[0] - pad) * SS), int((position[1] - pad) * SS)))


def draw_identity(image, draw, player):
    x, _ = ORIGIN[player]
    if player == "fly":
        draw.text((x * SS, 58 * SS), "🪰", font=ImageFont.truetype(FONT_EMOJI, 52 * SS), fill=TEXT, anchor="lm",
                  embedded_color=True)
        draw.text(((x + 67) * SS, 58 * SS), "Fly", font=font(54, True), fill=TEXT, anchor="lm")
    else:
        logo = Image.open(ROOT / "media" / "typesafe-logo.png").convert("RGBA").resize((54 * SS, 54 * SS), Image.Resampling.LANCZOS)
        image.alpha_composite(logo, (x * SS, 31 * SS))
        draw.text(((x + 70) * SS, 58 * SS), "Jev", font=font(54, True), fill=TEXT, anchor="lm")


def draw_progress(draw, player, status):
    x, _ = ORIGIN[player]
    width, gap = 45, 11
    start = x + BOARD - len(status) * width - (len(status) - 1) * gap
    for i, state in enumerate(status):
        box = (start + i * (width + gap), 49, start + i * (width + gap) + width, 67)
        if state == "won":
            rounded(draw, box, 6, ACCENT)
        elif state == "lost":
            rounded(draw, box, 6, DANGER)
        elif state == "current":
            rounded(draw, box, 6, BG, outline=ACCENT, width=3)
        else:
            rounded(draw, box, 6, GRID)


def draw_finish(image, player, state, alpha):
    if not (state["exploded"] is not None or state["won"]) or alpha <= 0:
        return
    x, y = ORIGIN[player]
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    tint = (237, 207, 114) if state["won"] else (238, 228, 218)
    draw.rounded_rectangle((x * SS, y * SS, (x + BOARD) * SS, (y + BOARD) * SS), radius=10 * SS,
                           fill=(*tint, int(210 * alpha)))
    title = "Cleared!" if state["won"] else "Game over"
    center_text(draw, (x + BOARD / 2, y + BOARD / 2), title, font(59, True),
                (119, 110, 101, int(255 * alpha)))
    image.alpha_composite(overlay)


def load_race(path=None):
    raw = json.loads(Path(path or ROOT / "results" / "showcase" / "race.json").read_text(encoding="utf8"))
    lanes = {"fly": [], "jev": []}
    for number, spec in enumerate(raw["stages"], 1):
        for player in lanes:
            record = spec[player]
            game, states = replay(record["seed"], record["moves"], n_mines=spec["n_mines"],
                                  opening_radius=spec["opening_radius"])
            if game.won != record.get("won", True):
                raise ValueError(f"stage {number} does not replay to the recorded {player} outcome")
            if len(record.get("flags", [])) != len(record["moves"]):
                raise ValueError(f"stage {number} has incomplete {player} flag snapshots")
            lanes[player].append({"game": game, "states": states, "beliefs": record["flags"],
                                  "seed": record["seed"], "player": player})
    return lanes


def move_weight(state):
    """A click that opens a wide cascade earns more of the clock than one that opens a single square."""
    return 1.0 + CASCADE_BONUS * min(1.0, max(0, len(state["opened"]) - 1) / 10)


def pace(lanes):
    """Hold the race to one length as the ladder gets longer, by scaling every move together."""
    units = []
    for stages in lanes.values():
        fixed = FIRST_READY + (len(stages) - 1) * NEXT_READY + len(stages) * CLEAR_HOLD
        weight = sum(move_weight(state) for stage in stages for state in stage["states"][1:])
        budget = TARGET_SECONDS - LEAD_HOLD - LEAD_FADE - OUTRO - INTRO - fixed
        units.append(budget / max(1e-6, weight))
    return float(np.clip(min(units), *MOVE_LIMITS))


def make_timeline(stages, unit):
    cursor, timeline = INTRO, []
    for index, stage in enumerate(stages):
        ready = FIRST_READY if index == 0 else NEXT_READY
        starts, durations = [cursor], [ready]
        cursor += ready
        for state in stage["states"][1:]:
            starts.append(cursor)
            durations.append(unit * move_weight(state))
            cursor += durations[-1]
        end = cursor + CLEAR_HOLD
        timeline.append({"start": starts[0], "state_starts": np.array(starts),
                         "durations": np.array(durations), "end": end})
        cursor = end
    return timeline, cursor


def lane_at(stages, timeline, time):
    index = next((i for i, segment in enumerate(timeline) if time < segment["end"]), len(timeline) - 1)
    segment, stage = timeline[index], stages[index]
    k = int(np.searchsorted(segment["state_starts"], time, side="right") - 1)
    k = max(0, min(k, len(stage["states"]) - 1))
    elapsed = (time - segment["state_starts"][k]) / segment["durations"][k]
    progress = 1.0 if k == 0 else float(np.clip(elapsed, 0, 1))
    travel = float(np.clip(elapsed, 0, 1))
    terminal = k == len(stage["states"]) - 1
    status = []
    for i, item in enumerate(timeline):
        if time >= item["end"] or (i == index and terminal):
            status.append("won" if stages[i]["game"].won else "lost")
        elif i == index:
            status.append("current")
        else:
            status.append("pending")
    return index, stage, k, progress, status, travel


def frame_at(lanes, timelines, time):
    image = Image.new("RGBA", (W * SS, H * SS), BG)
    draw = ImageDraw.Draw(image)
    for player in ("fly", "jev"):
        _, stage, k, progress, status, travel = lane_at(lanes[player], timelines[player], time)
        states, beliefs, game = stage["states"], stage["beliefs"], stage["game"]
        state = states[k]
        draw_identity(image, draw, player)
        draw_progress(draw, player, status)
        flag_index = min(k - 1, len(beliefs) - 1)
        flags = {tuple(x) for x in beliefs[flag_index]} if beliefs and k > 0 else set()
        draw_board(draw, player, state, states[max(0, k - 1)], progress, game, flags)
        draw_cursor(image, player, *cursor_at(stage, k, travel, progress))
        draw_finish(image, player, state, np.clip((progress - 0.42) / 0.35, 0, 1))
    return image.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)


def sound_events(lanes, timelines):
    events = []
    for player in ("fly", "jev"):
        pan = -0.58 if player == "fly" else 0.58
        for stage_index, (stage, segment) in enumerate(zip(lanes[player], timelines[player])):
            if stage_index:
                events.append((segment["start"] + 0.03, "stage", pan, 0))
            for k, state in enumerate(stage["states"][1:], 1):
                at = float(segment["state_starts"][k])
                events.append((at, "click", pan, 0))
                events.append((at + 0.035, "flag", pan, 0))
                if state["exploded"] is not None:
                    events.append((at + 0.08, "boom", pan, 0))
                elif state["won"]:
                    events.append((at + 0.09, "win", pan, 0))
                elif len(state["opened"]) > 1:
                    events.append((at + 0.07, "reveal", pan, len(state["opened"])))
    return events


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "renders" / "fly-vs-jev-race.mp4"
    fps = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    lanes = load_race(sys.argv[3] if len(sys.argv) > 3 else None)
    unit = pace(lanes)
    timelines, finishes = {}, {}
    for player in lanes:
        timelines[player], finishes[player] = make_timeline(lanes[player], unit)
    race = max(finishes.values()) + OUTRO
    lead = LEAD_HOLD + LEAD_FADE
    total = lead + race
    out.parent.mkdir(parents=True, exist_ok=True)
    silent = out.with_suffix(".silent.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "slow",
                           "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(silent)], stdin=subprocess.PIPE)
    frames = int(total * fps)
    finish_frame = frame_at(lanes, timelines, race - OUTRO)
    opening = frame_at(lanes, timelines, 0)
    for i in range(frames):
        time = i / fps
        if time < LEAD_HOLD:
            image = finish_frame
        elif time < lead:
            image = Image.blend(finish_frame, opening, (time - LEAD_HOLD) / LEAD_FADE)
        else:
            image = frame_at(lanes, timelines, time - lead)
        ff.stdin.write(image.tobytes())
        if i % 300 == 0: print(f"frame {i}/{frames}", flush=True)
    ff.stdin.close(); ff.wait()
    if ff.returncode: raise RuntimeError(f"ffmpeg exited {ff.returncode}")
    events = [(at + lead, kind, pan, amount) for at, kind, pan, amount in sound_events(lanes, timelines)]
    wav = out.with_suffix(".wav")
    write_wav(wav, mix(events, total))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    silent.unlink(); wav.unlink()
    passed = {p: sum(stage["game"].won for stage in lanes[p]) for p in lanes}
    winner = max(lanes, key=lambda p: (passed[p], -finishes[p]))
    print(f"wrote {out}: {total:.1f}s ({lead:.1f}s lead-in), {len(lanes['fly'])} stages, "
          f"fly passed {passed['fly']} in {finishes['fly']:.1f}s, jev passed {passed['jev']} in "
          f"{finishes['jev']:.1f}s, {winner} wins")


if __name__ == "__main__":
    main()
