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
    lines += [str(n + 1), f"{stamp(step['start'])} --> {stamp(end)}", step["say"], ""]
(d / "captions.srt").write_text("\n".join(lines))

inputs, filters = ["-i", str(d / "raw.webm")], []
for n, step in enumerate(steps):
    inputs += ["-i", str(d / "voice" / f"{step['id']}.wav")]
    ms = int(step["start"] * 1000)
    filters.append(f"[{n + 1}:a]adelay={ms}|{ms},apad[a{n}]")
mix = "".join(f"[a{n}]" for n in range(len(steps))) + f"amix=inputs={len(steps)}:normalize=0:duration=longest[voice]"
style = ("FontName=DejaVu Sans,FontSize=15,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=4,"
         "Outline=0,Shadow=0,MarginV=26,Alignment=2")
video = f"[0:v]subtitles={d / 'captions.srt'}:force_style='{style}',fps=25,format=yuv420p[v]"
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
       "-ac", "1"]
cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters + [mix, video]),
       "-map", "[v]", "-map", "[voice]", "-t", f"{timeline['end']:.2f}", *ENC, str(d / "main.mp4")]
subprocess.run(cmd, check=True)


def card_clip(name: str, minimum: float) -> Path | None:
    """A still card with its spoken line, faded in and out."""
    image, voice = d / f"{name}.png", d / "voice" / f"_{name}.wav"
    if not image.exists():
        return None
    length = max(minimum, durations.get(f"_{name}", 0) + 1.2)
    audio = (["-i", str(voice)] if voice.exists() else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono"])
    clip = d / f"{name}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", f"{length:.2f}", "-i", str(image), *audio,
                    "-filter_complex",
                    f"[0:v]fps=25,format=yuv420p,fade=in:st=0:d=0.5,fade=out:st={length - 0.5:.2f}:d=0.5[v];"
                    f"[1:a]adelay=400|400,apad,aresample=48000[a]",
                    "-map", "[v]", "-map", "[a]", "-t", f"{length:.2f}", *ENC, str(clip)], check=True)
    return clip


parts = [p for p in (card_clip("intro", 3.5), d / "main.mp4", card_clip("outro", 4.5)) if p]
streams = "".join(f"[{n}:v][{n}:a]" for n in range(len(parts)))
cmd = ["ffmpeg", "-y", "-v", "error"] + [x for p in parts for x in ("-i", str(p))] + [
    "-filter_complex", f"{streams}concat=n={len(parts)}:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", *ENC,
    "-movflags", "+faststart", str(d / "prism_scan_demo.mp4")]
subprocess.run(cmd, check=True)
print("wrote", d / "prism_scan_demo.mp4")
