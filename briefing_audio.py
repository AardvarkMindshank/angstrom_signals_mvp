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


def bed_for(weather: str | None) -> Path:
    """The music bed for the morning's weather (briefing_bed_<weather>.mp3), else the general one."""
    if weather:
        own = HERE / "video" / "music" / f"briefing_bed_{weather}.mp3"
        if own.exists():
            return own
    return BED
MODELS = HERE / "out" / "video" / "voice_model"
THEME_VOLUME = 0.5
INTRO = 4.5                     # seconds of music before the voice starts
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


LOUD, UNDER = 0.55, 0.10      # the weather music on its own, and under the voice
RAMP = 1.5                    # seconds to dip under the voice, and to swell back


def mix_command(voice_wav: Path, out_mp3: Path, voice_seconds: float, theme: Path = THEME, bed: Path = BED) -> list[str]:
    """The ffmpeg command. With a music bed (the morning's weather track): the music opens loud, dips under the voice,
    swells back for the close and fades out. Without one: the theme's opening and ending around the voice."""
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(voice_wav)]
    parts = [f"[0:a]aresample=48000,aformat=channel_layouts=mono,adelay={int(INTRO * 1000)},apad[v]"]
    names = ["[v]"]
    if bed.exists():
        total = INTRO + voice_seconds + OUTRO
        start, end = INTRO - 0.4, INTRO + voice_seconds + 0.3          # the dip, around the voice
        vol = (f"if(lt(t,{start:.2f}),{LOUD},if(lt(t,{start + RAMP:.2f}),{LOUD}-({LOUD}-{UNDER})*(t-{start:.2f})/{RAMP},"
               f"if(lt(t,{end:.2f}),{UNDER},if(lt(t,{end + RAMP:.2f}),{UNDER}+({LOUD}-{UNDER})*(t-{end:.2f})/{RAMP},"
               f"{LOUD}))))")
        args += ["-stream_loop", "-1", "-i", str(bed)]
        parts.append(f"[1:a]aresample=48000,aformat=channel_layouts=mono,atrim=0:{total:.2f},asetpts=PTS-STARTPTS,"
                     f"volume='{vol}':eval=frame,afade=t=in:st=0:d=0.8,afade=t=out:st={total - 2.5:.2f}:d=2.5[b]")
        names.append("[b]")
    else:
        total = INTRO + voice_seconds + OUTRO - OVERLAP
        if theme.exists():
            args += ["-i", str(theme), "-sseof", f"-{OUTRO:.2f}", "-i", str(theme)]
            parts.append(f"[1:a]aresample=48000,aformat=channel_layouts=mono,volume={THEME_VOLUME},"
                         f"atrim=0:{INTRO + 2.5:.2f},afade=t=out:st={INTRO - 0.3:.2f}:d=2.8[ti]")
            begin = INTRO + voice_seconds - OVERLAP
            parts.append(f"[2:a]aresample=48000,aformat=channel_layouts=mono,volume={THEME_VOLUME},"
                         f"afade=t=in:st=0:d=1.2,adelay={int(begin * 1000)}[to]")
            names += ["[ti]", "[to]"]
    graph = ";".join(parts) + f";{''.join(names)}amix=inputs={len(names)}:normalize=0:duration=longest,atrim=0:{total:.2f}[a]"
    return args + ["-filter_complex", graph, "-map", "[a]", "-ac", "1", "-ar", "24000", "-b:a", BITRATE,
                   str(out_mp3)]


def length(voice_seconds: float, bed: Path) -> float:
    return INTRO + voice_seconds + OUTRO - (0 if bed.exists() else OVERLAP)


def make(script: str, out_mp3: Path, voice: str = "bf_emma", work: Path | None = None, weather: str | None = None) -> float:
    """Speak and mix one briefing; returns its length in seconds."""
    work = work or out_mp3.parent
    wav = work / (out_mp3.stem + "_voice.wav")
    seconds = speak(script, wav, voice)
    bed = bed_for(weather)
    subprocess.run(mix_command(wav, out_mp3, seconds, bed=bed), check=True)
    wav.unlink(missing_ok=True)
    return length(seconds, bed)


if __name__ == "__main__":
    print(round(make(Path(sys.argv[1]).read_text(), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "bf_emma"), 1))
