"""Render the race and refresh every committed media file. usage: publish.py [fps]

Writes media/fly-vs-jev.mp4, the README GIF, and the opening and closing stills, so the
published assets always come from one render of the current race record.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "media"
FPS = sys.argv[1] if len(sys.argv) > 1 else "60"
GIF_WIDTH, GIF_FPS = 760, 15  # matches the width the README renders it at


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def main():
    MEDIA.mkdir(exist_ok=True)
    mp4 = MEDIA / "fly-vs-jev.mp4"
    subprocess.run([sys.executable, "-X", "utf8", "-u", str(ROOT / "video" / "render.py"), str(mp4), FPS],
                   check=True, cwd=ROOT)

    filters = (f"fps={GIF_FPS},scale={GIF_WIDTH}:-1:flags=lanczos,"
               "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3")
    ffmpeg("-i", str(mp4), "-vf", filters, "-loop", "0", str(MEDIA / "fly-vs-jev-ladder.gif"))

    ffmpeg("-ss", "0.5", "-i", str(mp4), "-frames:v", "1", "-q:v", "3", str(MEDIA / "first-frame.jpg"))
    ffmpeg("-sseof", "-0.4", "-i", str(mp4), "-frames:v", "1", "-q:v", "3", str(MEDIA / "final.jpg"))

    for path in (mp4, MEDIA / "fly-vs-jev-ladder.gif", MEDIA / "first-frame.jpg", MEDIA / "final.jpg"):
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
