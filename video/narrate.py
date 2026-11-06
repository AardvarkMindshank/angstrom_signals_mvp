"""Voice for each step of video/script.json: out/video/voice/<id>.wav and durations.json (seconds).
Uses the Piper neural voice when available, else espeak-ng."""

import json
import subprocess
import sys
import wave
from pathlib import Path

script = json.loads(Path("video/script.json").read_text())
out = Path(sys.argv[1] if len(sys.argv) > 1 else "out/video") / "voice"
out.mkdir(parents=True, exist_ok=True)
model = Path("out/video/voice_model/en_US-lessac-medium.onnx")
voice = None
try:
    from piper import PiperVoice

    voice = PiperVoice.load(str(model))
    print("voice: Piper en_US-lessac-medium")
except Exception as exc:
    print(f"voice: espeak-ng ({exc})")
durations = {}
for step in script["steps"]:
    path = out / f"{step['id']}.wav"
    if voice is not None:
        with wave.open(str(path), "wb") as wf:
            voice.synthesize_wav(step["say"], wf)
    else:
        subprocess.run(["espeak-ng", "-v", "en-us", "-s", "155", "-w", str(path), step["say"]], check=True)
    with wave.open(str(path)) as wf:
        durations[step["id"]] = wf.getnframes() / wf.getframerate()
(out.parent / "durations.json").write_text(json.dumps(durations, indent=1))
print(durations)
