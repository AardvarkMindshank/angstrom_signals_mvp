"""Combine the recording, the voice and burned-in subtitles into out/video/prism_scan_demo.mp4."""

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
video = f"[0:v]subtitles={d / 'captions.srt'}:force_style='{style}',format=yuv420p[v]"
cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters + [mix, video]),
       "-map", "[v]", "-map", "[voice]", "-t", f"{timeline['end']:.2f}",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "128k",
       "-movflags", "+faststart", str(d / "prism_scan_demo.mp4")]
subprocess.run(cmd, check=True)
print("wrote", d / "prism_scan_demo.mp4")
