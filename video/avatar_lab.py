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
    if isinstance(value, str) and value.startswith("repo:"):
        return _data_uri(Path(value[5:]))          # a picked image kept in the repo (invented characters only)
    if isinstance(value, str) and value.startswith("reports:"):    # a plain file on the reports branch (invented only)
        import subprocess, tempfile
        data = subprocess.run(["git", "show", f"origin/reports:{value[8:]}"], capture_output=True, check=True).stdout
        tmp = Path(tempfile.mkdtemp()) / Path(value[8:]).name
        tmp.write_bytes(data)
        return _data_uri(tmp)
    if isinstance(value, str) and value.startswith("out:") and out is not None:
        return _data_uri(out / value[4:])          # a file made by an earlier job in the same spec
    if isinstance(value, dict):
        return {k: _resolve(v, inputs, out) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, inputs, out) for v in value]   # several pictures (e.g. two characters in one scene)
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
                                  lang=job.get("lang") or ("en-gb" if voice.startswith("b") else "en-us"))
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
    pad = np.zeros(int(rate * 0.12), dtype=np.int16)             # a short breath before and after
    path = out / f"{job['id']}.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(np.concatenate([pad, pcm, pad]).tobytes())
    if job.get("pitch"):
        pitch_shift(path, float(job["pitch"]))
    return [path]


def pitch_shift(path: Path, semitones: float) -> None:
    """Raise (+) or lower (-) a voice by semitones, keeping its speed (ffmpeg), in place. The same as the daily video."""
    import subprocess
    import wave

    with wave.open(str(path)) as wf:
        rate = wf.getframerate()
    f = 2 ** (semitones / 12)
    tmp = path.with_suffix(".shift.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-af",
                    f"asetrate={rate}*{f},aresample={rate},atempo={1 / f}", str(tmp)], check=True)
    tmp.replace(path)


def _envelope(pcm, rate: int):
    import numpy as np
    hop = rate // 50                                              # 20 ms steps
    n = len(pcm) // hop
    e = np.sqrt((pcm[: n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(axis=1))
    return (e - e.mean()) / (e.std() + 1e-9)


def _wav_pcm(wav: bytes):
    import io
    import wave

    import numpy as np
    with wave.open(io.BytesIO(wav)) as wf:
        return np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16), wf.getframerate()


def _clip_pcm(video: Path, rate: int):
    import subprocess

    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16)


def recover(jobs: list, inputs: Path, outdir: Path, key: str, window: str) -> int:
    """Fetch clips fal already made (and were paid for) but that were lost on the way back: lists that model's
    successful requests in the window "<start>,<end>" (UTC), downloads each clip and matches it to a job by its sound
    (the voice line's loudness pattern). Needs the voice lines made first (free). Nothing new is made on fal."""
    import numpy as np
    start, end = window.split(",")
    head = {"Authorization": f"Key {key}"}
    want = {}
    for j in jobs:
        if "speak" in j or "audio_url" not in j.get("input", {}):
            continue
        a = j["input"]["audio_url"]
        wav = (outdir / a[4:]).read_bytes() if a.startswith("out:") else (inputs / a[5:]).read_bytes()
        pcm, rate = _wav_pcm(wav)
        want[j["id"]] = (j["model"], _envelope(pcm, rate), rate)
    found, tmp = 0, outdir / "_clip.mp4"
    for model in sorted({m for m, _, _ in want.values()}):
        cursor, items = None, []
        while True:
            q = {"endpoint_id": model, "start": start, "end": end, "status": "success", "limit": 100}
            if cursor:
                q["cursor"] = cursor
            q["expand"] = "payloads"
            r = requests.get("https://api.fal.ai/v1/models/requests/by-endpoint", headers=head, params=q, timeout=300)
            _check(r)
            body = r.json()
            items += body.get("items") or []
            cursor = body.get("next_cursor")
            if not cursor:
                break
        print(f"{model}: {len(items)} finished request(s) in the window", flush=True)
        best = {}                                                  # job id -> (score, video link)
        for n, it in enumerate(items):
            res = it.get("json_output") or {}
            if not res.get("video"):
                continue
            try:
                tmp.write_bytes(requests.get(res["video"]["url"], timeout=300).content)
            except Exception:
                continue
            scores, heard = [], {}
            for jid, (m, env, rate) in want.items():
                if m != model:
                    continue
                if rate not in heard:
                    heard[rate] = _envelope(_clip_pcm(tmp, rate), rate)
                got = heard[rate]
                k = min(len(env), len(got))
                if k < 25 or abs(len(env) - len(got)) > max(15, 0.4 * len(env)):
                    continue
                lag = max(range(0, len(got) - k + 1) if len(got) > k else [0],
                          key=lambda L: float(np.dot(env[:k], got[L:L + k])))
                scores.append((float(np.corrcoef(env[:k], got[lag:lag + k])[0, 1]), jid))
            if not scores:
                continue
            scores.sort(reverse=True)
            score, jid = scores[0]
            margin = score - (scores[1][0] if len(scores) > 1 else 0)
            print(f"item {n}: best match {score:.2f} (next {margin:.2f} lower)", flush=True)
            if score >= 0.8 and margin >= 0.1 and score > best.get(jid, (0, ""))[0]:
                best[jid] = (score, res["video"]["url"])
        for jid, (_score, url) in best.items():
            path = outdir / f"{jid}_1.mp4"
            if not path.exists():
                path.write_bytes(requests.get(url, timeout=300).content)
                found += 1
                print(f"{jid}: recovered", flush=True)
    tmp.unlink(missing_ok=True)
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
