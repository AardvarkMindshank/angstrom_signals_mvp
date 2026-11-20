"""🎬 The marketing teaser's narration (20 Nov 2026): each line of video/teaser/lines.json in each listed Kokoro voice,
as out/teaser_voice/<voice>/<line>.wav. Run by .github/workflows/teaser-voice.yml (Kokoro needs Python 3.12); the
video itself is put together from these files."""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MODELS = HERE.parent / "out" / "video" / "voice_model"


def main(out: str = "out/teaser_voice") -> int:
    from kokoro_onnx import Kokoro

    spec = json.loads((HERE / "teaser" / "lines.json").read_text())
    kokoro = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
    for voice in spec["voices"]:
        folder = Path(out) / voice
        folder.mkdir(parents=True, exist_ok=True)
        for key, text in spec["lines"].items():
            samples, rate = kokoro.create(text, voice=voice, speed=float(spec.get("speed", 1.0)),
                                          lang="en-gb" if voice.startswith("b") else "en-us")
            pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
            with wave.open(str(folder / f"{key}.wav"), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(rate)
                wf.writeframes(pcm.tobytes())
            print(f"{voice} {key}: {len(pcm) / rate:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
