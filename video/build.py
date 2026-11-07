"""Combine the opening card, the recording (with its voice and burned-in subtitles) and the closing card into
out/video/prism_scan_demo.mp4."""

import json
import subprocess
import sys
from pathlib import Path

d = Path(sys.argv[1] if len(sys.argv) > 1 else "out/video")
timeline = json.loads((d / "timeline.json").read_text())
durations = json.loads((d / "durations.json").read_text())


def stamp(sec: float) -> str:
    h, rem = divmod(max(0.0, sec), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


steps = timeline["steps"]
lines = []
for n, step in enumerate(steps):
    end = steps[n + 1]["start"] if n + 1 < len(steps) else timeline["end"]
    end = min(end, step["start"] + durations[step["id"]] + 0.6)
    words = " ".join(step["say"].replace("|", " ").split())          # pause marks are for the voice only
    lines += [str(n + 1), f"{stamp(step['start'])} --> {stamp(end)}", words, ""]
(d / "captions.srt").write_text("\n".join(lines))



def check_captions_clear(app_bottom: int = 610, gap: int = 6) -> None:
    """Draw every caption alone on a black frame, exactly as the video does, and stop if any of it reaches the app
    picture (rows 0-609): captions must never cover the screen."""
    from PIL import Image

    probe = d / "_captions_probe.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=black:size=1280x720:rate=4:d={timeline['end'] + 1:.2f}", "-vf",
                    f"subtitles={d / 'captions.srt'}:force_style='{style}'", str(probe)], check=True)
    for n, step in enumerate(steps):
        frame = d / f"_probe_{n}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{step['start'] + 0.5:.2f}", "-i", str(probe),
                        "-frames:v", "1", str(frame)], check=True)
        im = Image.open(frame).convert("L")
        top = next((y for y in range(im.height) if max(im.crop((0, y, im.width, y + 1)).getdata()) > 80), None)
        frame.unlink()
        if top is not None and top < app_bottom + gap:
            raise SystemExit(f"Caption {n + 1} reaches row {top}, over the app (ends at row {app_bottom - 1}). "
                             f"Shorten it: \"{step['say'][:60]}…\"")
    probe.unlink()
    print("Captions checked: none reaches the app picture.")


inputs, filters = ["-i", str(d / "raw.webm")], []
for n, step in enumerate(steps):
    inputs += ["-i", str(d / "voice" / f"{step['id']}.wav")]
    ms = int(step["start"] * 1000)
    filters.append(f"[{n + 1}:a]adelay={ms}|{ms},apad[a{n}]")
mix = "".join(f"[a{n}]" for n in range(len(steps))) + f"amix=inputs={len(steps)}:normalize=0:duration=longest[voice]"
# Captions sit in a dark band under the app (recorded at 1280 x 610), never over it: 1280 x 720 in all.
style = ("FontName=DejaVu Sans,FontSize=12.5,PrimaryColour=&H00FFFFFF,BorderStyle=1,Outline=0,Shadow=0,"
         "MarginV=9,Alignment=2")
check_captions_clear()
video = (f"[0:v]scale=1280:610,pad=1280:720:0:0:color=0x0b1220,"
         f"subtitles={d / 'captions.srt'}:force_style='{style}',fps=25,format=yuv420p[v]")
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
       "-ac", "1"]
cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters + [mix, video]),
       "-map", "[v]", "-map", "[voice]", "-t", f"{timeline['end']:.2f}", *ENC, str(d / "main.mp4")]
subprocess.run(cmd, check=True)


MUSIC = Path(__file__).resolve().parent / "music" / "theme.mp3"     # optional; licence noted in video/music/README.md
MUSIC_VOLUME = 0.45


def card_clip(name: str, minimum: float) -> Path | None:
    """A still card with its spoken line, faded in and out."""
    image, voice = d / f"{name}.png", d / "voice" / f"_{name}.wav"
    if not image.exists():
        return None
    length = max(minimum, durations.get(f"_{name}", 0) + 1.2)
    audio = (["-i", str(voice)] if voice.exists() else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono"])
    clip = d / f"{name}.mp4"
    fade = f"[0:v]fps=25,format=yuv420p,fade=in:st=0:d=0.5,fade=out:st={length - 0.5:.2f}:d=0.5[v];"
    speech = "[1:a]adelay=400|400,apad,aresample=48000"
    if MUSIC.exists():
        # The theme under the card: its opening for the intro, its ending for the outro, below the voice.
        music = (["-i", str(MUSIC)] if name == "intro" else ["-sseof", f"-{length:.2f}", "-i", str(MUSIC)])
        audio += music
        mix = (f"{speech}[s];[2:a]aresample=48000,aformat=channel_layouts=mono,volume={MUSIC_VOLUME},"
               f"afade=t=in:st=0:d=0.15,afade=t=out:st={length - 0.9:.2f}:d=0.9,apad[m];"
               f"[s][m]amix=inputs=2:normalize=0:duration=first[a]")
    else:
        mix = f"{speech}[a]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", f"{length:.2f}", "-i", str(image), *audio,
                    "-filter_complex", fade + mix,
                    "-map", "[v]", "-map", "[a]", "-t", f"{length:.2f}", *ENC, str(clip)], check=True)
    return clip


parts = [p for p in (card_clip("intro", 3.5), d / "main.mp4", card_clip("outro", 4.5)) if p]
streams = "".join(f"[{n}:v][{n}:a]" for n in range(len(parts)))
cmd = ["ffmpeg", "-y", "-v", "error"] + [x for p in parts for x in ("-i", str(p))] + [
    "-filter_complex", f"{streams}concat=n={len(parts)}:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", *ENC,
    "-movflags", "+faststart", str(d / "prism_scan_demo.mp4")]
subprocess.run(cmd, check=True)
print("wrote", d / "prism_scan_demo.mp4")
