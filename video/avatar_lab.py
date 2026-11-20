"""🎭 Avatar lab (20 Nov 2026): makes the presenter test images and clips on fal.ai for the daily video, from a
spec of jobs (video/avatar_lab/*.json). Run by .github/workflows/avatar-lab.yml, which has FAL_KEY.

Each job: {"id", "model" (a fal endpoint, e.g. fal-ai/flux-pro/kontext/text-to-image), "input" {…}} where any
input value "file:<name>" is replaced by that file (from the inputs folder) as a data URI, so a private photo never
needs a public link. Outputs (images and videos) are saved as <id>_<n>.<ext>. The log prints no prompts."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import requests

API = "https://queue.fal.run"


def _data_uri(path: Path) -> str:
    kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{kind};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _resolve(value, inputs: Path, out: Path | None = None):
    if isinstance(value, str) and value.startswith("file:"):
        return _data_uri(inputs / value[5:])
    if isinstance(value, str) and value.startswith("out:") and out is not None:
        return _data_uri(out / value[4:])          # a file made by an earlier job in the same spec
    if isinstance(value, dict):
        return {k: _resolve(v, inputs, out) for k, v in value.items()}
    return value


def run_job(job: dict, inputs: Path, out: Path, key: str) -> list[Path]:
    head = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    r = requests.post(f"{API}/{job['model']}", headers=head, json=_resolve(job["input"], inputs, out), timeout=300)
    r.raise_for_status()
    q = r.json()
    status_url, response_url = q["status_url"], q["response_url"]
    for _ in range(240):                                   # up to 20 minutes (video models are slow)
        s = requests.get(status_url, headers=head, timeout=60).json()
        if s.get("status") == "COMPLETED":
            break
        time.sleep(5)
    else:
        raise TimeoutError("fal job did not finish")
    res = requests.get(response_url, headers=head, timeout=120)
    res.raise_for_status()
    body = res.json()
    media = [m["url"] for m in (body.get("images") or [])] + ([body["video"]["url"]] if body.get("video") else [])
    saved = []
    for n, url in enumerate(media, 1):
        ext = Path(url.split("?")[0]).suffix or ".bin"
        path = out / f"{job['id']}_{n}{ext}"
        path.write_bytes(requests.get(url, timeout=300).content)
        saved.append(path)
    return saved


def speak_job(job: dict, out: Path) -> list[Path]:
    """{"id", "speak": text, "voice", "speed"}: the free Kokoro voice, saved as <id>.wav (needs the voice model)."""
    import wave

    import numpy as np
    from kokoro_onnx import Kokoro

    models = Path("out/video/voice_model")
    kokoro = Kokoro(str(models / "kokoro-v1.0.onnx"), str(models / "voices-v1.0.bin"))
    voice = job.get("voice", "bm_george")
    samples, rate = kokoro.create(job["speak"], voice=voice, speed=float(job.get("speed", 1.0)),
                                  lang="en-gb" if voice.startswith("b") else "en-us")
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
    pad = np.zeros(int(rate * 0.3), dtype=np.int16)              # a breath before and after
    path = out / f"{job['id']}.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(np.concatenate([pad, pcm, pad]).tobytes())
    return [path]


def main(spec: str, inputs: str = "lab_in", out: str = "out/avatar_lab") -> int:
    key = os.environ["FAL_KEY"]
    jobs = json.loads(Path(spec).read_text())["jobs"]
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for job in jobs:
        try:
            files = speak_job(job, outdir) if "speak" in job else run_job(job, Path(inputs), outdir, key)
            print(f"{job['id']}: {len(files)} file(s)")
        except Exception as exc:
            failed += 1
            print(f"{job['id']}: failed ({type(exc).__name__}: {str(exc)[:160]})")
    return 1 if failed == len(jobs) else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
