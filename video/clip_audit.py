"""🔍 Clip audit (24 Nov 2026): for every presenter clip in the library, how long it runs, where its voice ends and
how much the daily video cuts off. Prints names and seconds only (no pictures, no sound), so it is safe for every
clip, the Captain's included. A clip still moving well after its voice ends, or one the cut would shorten a lot, is
listed for a look.

🧾 The set check (26 Nov 2026): every clip the daily video can ask for is in the library. Each presenter in the draw
needs both takes of every line (the video picks take 1 or 2 at random, so a missing take 2 would stop that day's
video); guests need their welcome and sign-off; the Rat's tags, the Cook's reveal and the bloopers are listed too.

    python video/clip_audit.py lib/avatar_lab
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import daily_video as dv  # noqa: E402

SKIP = ("blooper_", "say_")


def missing_clips(library: Path) -> list[tuple[str, str]]:
    """[(clip name, what happens without it)] for every clip the daily video can ask for that the library lacks."""
    out = []
    for who in dv.CHANCES:
        for line in dv.SET_LINES:
            for take in (1, 2):
                name = f"{who}_{line}_{take}_1.mp4"
                if not (library / name).exists():
                    why = ("presenter left out of the draw" if take == 1
                           else "the video fails on a day this take is picked")
                    out.append((name, why))
    for guest in dv.GUESTS:
        for line in ("welcome", "signoff"):
            name = f"{guest}_{line}_1_1.mp4"
            if not (library / name).exists():
                out.append((name, "guest skipped on their day"))
    extras = [(f"ratd_tag_{t}_1.mp4", "the Rat's tag skipped that day") for t in (1, 2)]
    extras += [(dv.COOK_REVEAL, "the Cook's reveal never plays")]
    extras += [(b, "this blooper never plays") for b in dv.BLOOPERS]
    out += [(n, why) for n, why in extras if not (library / n).exists()]
    return out


def main(folder: str) -> int:
    gaps = missing_clips(Path(folder))
    print(f"Set check: {len(gaps)} clip(s) missing")
    for name, why in gaps:
        print(f"  missing {name:40s} {why}")
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
