"""🔍 Clip audit (24 Nov 2026): for every presenter clip in the library, how long it runs, where its voice ends and
how much the daily video cuts off. Prints names and seconds only (no pictures, no sound), so it is safe for every
clip, the Captain's included. A clip still moving well after its voice ends, or one the cut would shorten a lot, is
listed for a look.

    python video/clip_audit.py lib/avatar_lab
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import daily_video as dv  # noqa: E402

SKIP = ("blooper_", "say_")


def main(folder: str) -> int:
    rows = []
    for clip in sorted(Path(folder).glob("*_1.mp4")):
        if clip.name.startswith(SKIP):
            continue
        whole = dv.duration(clip)
        used = dv.speech_seconds(clip)
        rows.append((clip.name, whole, used, whole - used))
    cut = [r for r in rows if r[3] >= 0.3]
    print(f"Clips: {len(rows)}; cut by 0.3 s or more at the end: {len(cut)}")
    for name, whole, used, gone in sorted(cut, key=lambda r: -r[3]):
        flag = "  <- look" if gone > 2.5 or used < 1.2 else ""
        print(f"{name:42s} runs {whole:5.2f} s, voice to {used:5.2f} s, cut {gone:4.2f} s{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "lib/avatar_lab"))
