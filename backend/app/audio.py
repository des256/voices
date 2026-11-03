"""Audio probing and decoding through ffmpeg/ffprobe."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000


@dataclass
class AudioInfo:
    duration: float
    codec: str


def probe(path: Path) -> AudioInfo:
    """Return duration and codec of the first audio stream; raise ValueError if the file is not decodable audio."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name:format=duration",
        "-of", "json", str(path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe is not installed") from exc
    if out.returncode != 0:
        raise ValueError("The file could not be read as audio.")
    info = json.loads(out.stdout or "{}")
    streams = info.get("streams") or []
    if not streams:
        raise ValueError("The file contains no audio stream.")
    try:
        duration = float(info.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise ValueError("The audio has no measurable duration.")
    return AudioInfo(duration=duration, codec=str(streams[0].get("codec_name", "unknown")))


def to_wav16k(src: Path, dst: Path) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt", "s16", str(dst)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to decode the audio: {out.stderr.strip()[:300]}")


def load_wav(path: Path) -> np.ndarray:
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if sr != SAMPLE_RATE:
        raise RuntimeError(f"expected {SAMPLE_RATE} Hz audio, got {sr}")
    return np.ascontiguousarray(data.mean(axis=1))
