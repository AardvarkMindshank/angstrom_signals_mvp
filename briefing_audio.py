"""
🎧 The morning briefing's sound: the script read by Kokoro (the training videos' free voice), then mixed with ffmpeg:
the theme's opening under the first seconds, an optional quiet music bed under the whole voice
(video/music/briefing_bed.mp3, looped), and the theme's ending under the close. Out: a small mono MP3.

    python briefing_audio.py script.txt out.mp3 [voice]
"""

from __future__ import annotations

import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
THEME = HERE / "video" / "music" / "theme.mp3"
BED = HERE / "video" / "music" / "briefing_bed.mp3"          # optional; licence noted in video/music/README.md
MODELS = HERE / "out" / "video" / "voice_model"
THEME_VOLUME = 0.5
BED_VOLUME = 0.08               # well under the voice
INTRO = 3.2                     # seconds of theme before the voice starts
OUTRO = 6.0                     # seconds of the theme's ending, overlapping the last words by OVERLAP
OVERLAP = 1.5
PAUSE = 0.28                    # between sentences groups
BITRATE = "64k"


def chunks(text: str, limit: int = 380) -> list[str]:
    """The script cut at sentence ends into pieces the voice reads well (at most `limit` characters)."""
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    out, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) + 1 > limit:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def speak(text: str, path: Path, voice: str = "bf_emma", models: Path = MODELS) -> float:
    """The script as a WAV file (mono); returns its length in seconds."""
    from kokoro_onnx import Kokoro

    kokoro = Kokoro(str(models / "kokoro-v1.0.onnx"), str(models / "voices-v1.0.bin"))
    lang = "en-gb" if voice.startswith("b") else "en-us"
    pieces, rate = [], 24000
    for part in chunks(text):
        samples, rate = kokoro.create(part, voice=voice, speed=1.0, lang=lang)
        pieces += [np.asarray(samples, dtype=np.float32), np.zeros(int(rate * PAUSE), dtype=np.float32)]
    audio = np.concatenate(pieces) if pieces else np.zeros(rate, dtype=np.float32)
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    return len(audio) / rate


def mix_command(voice_wav: Path, out_mp3: Path, voice_seconds: float, theme: Path = THEME, bed: Path = BED) -> list[str]:
    """The ffmpeg command: theme opening, the voice (with a quiet looped bed if there is one), theme ending."""
    total = INTRO + voice_seconds + OUTRO - OVERLAP
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(voice_wav)]
    parts = [f"[0:a]aresample=48000,aformat=channel_layouts=mono,adelay={int(INTRO * 1000)},apad[v]"]
    names = ["[v]"]
    n = 1
    if theme.exists():
        args += ["-i", str(theme), "-sseof", f"-{OUTRO:.2f}", "-i", str(theme)]
        parts.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=mono,volume={THEME_VOLUME},"
                     f"atrim=0:{INTRO + 2.5:.2f},afade=t=out:st={INTRO - 0.3:.2f}:d=2.8[ti]")
        start = INTRO + voice_seconds - OVERLAP
        parts.append(f"[{n + 1}:a]aresample=48000,aformat=channel_layouts=mono,volume={THEME_VOLUME},"
                     f"afade=t=in:st=0:d=1.2,adelay={int(start * 1000)}[to]")
        names += ["[ti]", "[to]"]
        n += 2
    if bed.exists():
        args += ["-stream_loop", "-1", "-i", str(bed)]
        parts.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=mono,volume={BED_VOLUME},"
                     f"atrim=0:{voice_seconds + 2:.2f},afade=t=in:st=0:d=2,afade=t=out:st={voice_seconds:.2f}:d=2,"
                     f"adelay={int((INTRO - 1) * 1000)}[b]")
        names.append("[b]")
    graph = ";".join(parts) + f";{''.join(names)}amix=inputs={len(names)}:normalize=0:duration=longest,atrim=0:{total:.2f}[a]"
    return args + ["-filter_complex", graph, "-map", "[a]", "-ac", "1", "-ar", "24000", "-b:a", BITRATE,
                   str(out_mp3)]


def make(script: str, out_mp3: Path, voice: str = "bf_emma", work: Path | None = None) -> float:
    """Speak and mix one briefing; returns its length in seconds."""
    work = work or out_mp3.parent
    wav = work / (out_mp3.stem + "_voice.wav")
    seconds = speak(script, wav, voice)
    subprocess.run(mix_command(wav, out_mp3, seconds), check=True)
    wav.unlink(missing_ok=True)
    return INTRO + seconds + OUTRO - OVERLAP


if __name__ == "__main__":
    print(round(make(Path(sys.argv[1]).read_text(), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "bf_emma"), 1))
