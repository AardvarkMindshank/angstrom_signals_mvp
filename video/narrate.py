"""Voice for each step of video/script.json: out/video/voice/<id>.wav and durations.json (seconds).

Voices, best first: Kokoro (open source, Apache 2.0, natural), then Piper, then espeak-ng. VOICE picks the Kokoro
voice (default bf_emma). With --samples, also writes short samples of a few Kokoro voices to compare.
"""

import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

script = json.loads(Path("video/script.json").read_text())
base = Path(sys.argv[1] if len(sys.argv) > 1 else "out/video")
out = base / "voice"
out.mkdir(parents=True, exist_ok=True)
models = base / "voice_model"
KOKORO_VOICE = os.environ.get("VOICE", "bf_emma")
SAMPLES = {"af_heart": "US, female", "am_michael": "US, male", "bf_emma": "UK, female", "bm_george": "UK, male"}


def write_wav(path, samples, rate):
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())


speak = None
try:
    from kokoro_onnx import Kokoro

    kokoro = Kokoro(str(models / "kokoro-v1.0.onnx"), str(models / "voices-v1.0.bin"))

    def speak(text, path, voice=KOKORO_VOICE):
        samples, rate = kokoro.create(text, voice=voice, speed=1.0, lang="en-gb" if voice.startswith("b") else "en-us")
        write_wav(path, samples, rate)
    print(f"voice: Kokoro {KOKORO_VOICE}")
except Exception as exc:
    print(f"Kokoro not available ({exc})")
if speak is None:
    try:
        from piper import PiperVoice

        piper = PiperVoice.load(str(models / "en_US-lessac-medium.onnx"))

        def speak(text, path, voice=None):
            with wave.open(str(path), "wb") as wf:
                piper.synthesize_wav(text, wf)
        print("voice: Piper en_US-lessac-medium")
    except Exception as exc:
        print(f"voice: espeak-ng ({exc})")

        def speak(text, path, voice=None):
            subprocess.run(["espeak-ng", "-v", "en-us", "-s", "155", "-w", str(path), text], check=True)

PAUSE = 0.35         # seconds of silence for each "|" in a line: "instantly, | in the daily summary"


def say(text, path):
    """Speak a line; a "|" marks a pause (each part is spoken separately, with silence between)."""
    parts = [p.strip() for p in str(text).split("|") if p.strip()]
    if len(parts) == 1:
        speak(parts[0], path)
        return
    chunks, rate = [], None
    for n, part in enumerate(parts):
        tmp = out / f"_part{n}.wav"
        speak(part, tmp)
        with wave.open(str(tmp)) as wf:
            rate, frames = wf.getframerate(), wf.readframes(wf.getnframes())
            chunks.append(np.frombuffer(frames, dtype=np.int16))
        tmp.unlink()
    silence = np.zeros(int(rate * PAUSE), dtype=np.int16)
    joined = np.concatenate([c for chunk in chunks for c in (chunk, silence)][:-1])
    write_wav(path, joined.astype(np.float32) / 32767, rate)


durations = {}
for step in script["steps"]:
    path = out / f"{step['id']}.wav"
    say(step["say"], path)
    with wave.open(str(path)) as wf:
        durations[step["id"]] = wf.getnframes() / wf.getframerate()
for key in ("intro", "outro"):                 # spoken over the opening and closing cards
    if script.get(f"{key}_say"):
        path = out / f"_{key}.wav"
        say(script[f"{key}_say"], path)
        with wave.open(str(path)) as wf:
            durations[f"_{key}"] = wf.getnframes() / wf.getframerate()
(base / "durations.json").write_text(json.dumps(durations, indent=1))
print(durations)

if "--samples" in sys.argv and "kokoro" in globals():
    line = ("Each asset gets Yes, No, or Unknown, with the line that decided it. "
            "To keep watching, give the scan a schedule.")
    for voice, words in SAMPLES.items():
        wav = base / f"sample_{voice}.wav"
        speak(f"{line}", wav, voice)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-b:a", "96k",
                        str(base / f"voice_sample_{voice}_{words.replace(', ', '_')}.mp3")], check=True)
