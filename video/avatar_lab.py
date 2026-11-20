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


def _check(r) -> None:
    """Raise with fal's own short reason (for example an empty balance), never the request itself."""
    if r.status_code >= 400:
        raise RuntimeError(f"fal {r.status_code}: {r.text[:200]}")


def run_job(job: dict, inputs: Path, out: Path, key: str) -> list[Path]:
    head = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    r = requests.post(f"{API}/{job['model']}", headers=head, json=_resolve(job["input"], inputs, out), timeout=300)
    _check(r)
    q = r.json()
    status_url, response_url = q["status_url"], q["response_url"]
    for _ in range(480):                                   # up to 40 minutes (video models queue when busy)
        s = requests.get(status_url, headers=head, timeout=60).json()
        if s.get("status") == "COMPLETED":
            break
        time.sleep(5)
    else:
        raise TimeoutError("fal job did not finish")
    res = requests.get(response_url, headers=head, timeout=120)
    _check(res)
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
    pad = np.zeros(int(rate * 0.12), dtype=np.int16)             # a short breath before and after
    path = out / f"{job['id']}.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(np.concatenate([pad, pcm, pad]).tobytes())
    return [path]


def _bytes_of(value: str) -> bytes:
    if value.startswith("data:"):
        return base64.b64decode(value.split(",", 1)[1])
    return requests.get(value, timeout=120).content


def _seconds(wav: bytes) -> float:
    import io
    import wave
    with wave.open(io.BytesIO(wav)) as wf:
        return wf.getnframes() / wf.getframerate()


def recover(jobs: list, inputs: Path, outdir: Path, key: str, window: str) -> int:
    """Fetch clips fal already made (and were paid for) but that were lost on the way back: lists that model's
    successful requests in the window "<start>,<end>" (UTC) and matches each to a job by its voice line's length and
    its picture. Needs the voice lines made first (free). Nothing new is made on fal."""
    import hashlib
    start, end = window.split(",")
    head = {"Authorization": f"Key {key}"}
    want = {}
    for j in jobs:
        if "speak" in j or "audio_url" not in j.get("input", {}):
            continue
        a, im = j["input"]["audio_url"], j["input"]["image_url"]
        wav = (outdir / a[4:]).read_bytes() if a.startswith("out:") else (inputs / a[5:]).read_bytes()
        pic = (outdir / im[4:]) if im.startswith("out:") else (inputs / im[5:])
        want[j["id"]] = (j["model"], round(_seconds(wav), 2), hashlib.sha256(pic.read_bytes()).hexdigest())
    found = 0
    for model in sorted({m for m, _, _ in want.values()}):
        cursor, items = None, []
        while True:
            q = {"endpoint_id": model, "start": start, "end": end, "status": "success", "expand": "payloads", "limit": 100}
            if cursor:
                q["cursor"] = cursor
            r = requests.get("https://api.fal.ai/v1/models/requests/by-endpoint", headers=head, params=q, timeout=300)
            _check(r)
            body = r.json()
            items += body.get("items") or []
            cursor = body.get("next_cursor")
            if not cursor:
                break
        print(f"{model}: {len(items)} finished request(s) in the window", flush=True)
        for it in items:
            inp, res = it.get("json_input") or {}, it.get("json_output") or {}
            if not (res.get("video") and inp.get("audio_url") and inp.get("image_url")):
                continue
            try:
                secs = round(_seconds(_bytes_of(inp["audio_url"])), 2)
                pic = hashlib.sha256(_bytes_of(inp["image_url"])).hexdigest()
            except Exception:
                continue
            hits = [i for i, (m, s_, h) in want.items() if m == model and abs(s_ - secs) <= 0.01 and h == pic]
            if not hits:
                hits = [i for i, (m, s_, _h) in want.items() if m == model and abs(s_ - secs) <= 0.01]
            if len(hits) != 1:
                continue
            path = outdir / f"{hits[0]}_1.mp4"
            if not path.exists():
                path.write_bytes(requests.get(res["video"]["url"], timeout=300).content)
                found += 1
                print(f"{hits[0]}: recovered", flush=True)
    print(f"Recovered {found} of {len(want)} clip(s).", flush=True)
    return 0 if found else 1


def main(spec: str, inputs: str = "lab_in", out: str = "out/avatar_lab") -> int:
    key = os.environ["FAL_KEY"]
    jobs = json.loads(Path(spec).read_text())["jobs"]
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    failed = 0

    def one(job):
        try:
            files = speak_job(job, outdir) if "speak" in job else run_job(job, Path(inputs), outdir, key)
            print(f"{job['id']}: {len(files)} file(s)", flush=True)
            return 0
        except Exception as exc:
            print(f"{job['id']}: failed ({type(exc).__name__}: {str(exc)[:160]})", flush=True)
            return 1

    # In stages: the voice lines first, then every fal job of a stage at once (up to 8 together); a job that uses an
    # earlier job's output ("out:…") waits for the next stage (job key "stage", default 0 for voice and images).
    from concurrent.futures import ThreadPoolExecutor

    speak = [j for j in jobs if "speak" in j]
    for job in speak:
        failed += one(job)
    if os.environ.get("RECOVER"):
        return recover(jobs, Path(inputs), outdir, key, os.environ["RECOVER"])
    rest = [j for j in jobs if "speak" not in j]
    for stage in sorted({int(j.get("stage", 0)) for j in rest}):
        batch = [j for j in rest if int(j.get("stage", 0)) == stage]
        with ThreadPoolExecutor(max_workers=12) as pool:
            failed += sum(pool.map(one, batch))
    return 1 if failed == len(jobs) else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
