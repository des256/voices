"""End-to-end analysis of one recording. Stages run sequentially and each model is released afterwards
so the whole job fits in a small CPU-only container."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import torch

from app import audio as audio_mod
from app import emotion, prosody, sentiment, transcribe
from app.models import EMOTION_CATEGORIES_MODEL, EMOTION_DIMENSIONS_MODEL, SENTIMENT_MODEL
from app.schema import Analysis, Segment, Window
from app.settings import Settings

Progress = Callable[[float, str], None]

WINDOW_MIN_SECONDS = 3.0
WINDOW_MAX_SECONDS = 20.0


def build_windows(segments: list[Segment], min_len: float = WINDOW_MIN_SECONDS, max_len: float = WINDOW_MAX_SECONDS) -> list[Window]:
    """Merge short transcript segments (and split very long ones) into windows of min_len..max_len seconds."""
    units: list[Window] = []
    for seg in segments:
        if seg.end - seg.start <= max_len or len(seg.words) < 2:
            units.append(Window(seg.start, seg.end, seg.text, len(seg.words)))
            continue
        group: list = []
        for w in seg.words:
            if group and w.end - group[0].start > max_len:
                units.append(Window(group[0].start, group[-1].end, " ".join(x.text for x in group), len(group)))
                group = []
            group.append(w)
        if group:
            units.append(Window(group[0].start, group[-1].end, " ".join(x.text for x in group), len(group)))

    windows: list[Window] = []
    for unit in units:
        if windows:
            last = windows[-1]
            if last.duration < min_len and unit.end - last.start <= max_len:
                last.end = unit.end
                last.text = f"{last.text} {unit.text}".strip()
                last.words += unit.words
                continue
        windows.append(unit)
    return windows


def _weighted(values: list[float], weights: list[float]) -> tuple[float, float]:
    if not values:
        return math.nan, math.nan
    v, w = np.asarray(values, dtype=float), np.asarray(weights, dtype=float)
    if w.sum() <= 0:
        w = np.ones_like(v)
    mean = float(np.average(v, weights=w))
    std = float(math.sqrt(np.average((v - mean) ** 2, weights=w)))
    return mean, std


def analyze(path: Path, file_name: str, report_progress: Progress, settings: Settings) -> Analysis:
    torch.set_num_threads(settings.threads)
    workdir = path.parent

    def progress(fraction: float, stage: str) -> None:
        report_progress(round(min(max(fraction, 0.0), 1.0), 3), stage)

    progress(0.0, "Decoding audio")
    wav_path = workdir / "audio16k.wav"
    audio_mod.to_wav16k(path, wav_path)
    signal = audio_mod.load_wav(wav_path)
    duration = len(signal) / audio_mod.SAMPLE_RATE

    progress(0.04, "Transcribing")
    transcript = transcribe.transcribe(signal, duration, settings, lambda f: progress(0.04 + 0.50 * f, "Transcribing"))

    progress(0.55, "Measuring pace and pauses")
    words = transcript.words
    pauses = prosody.pause_stats(words, threshold=settings.pause_threshold)
    rate = prosody.rate_stats(words, pause_seconds=pauses.total_seconds)
    fillers = prosody.filler_stats(words, transcript.language, rate.speech_span_seconds)

    progress(0.58, "Analyzing pitch and loudness")
    track = prosody.acoustics(wav_path)

    windows = build_windows(transcript.segments)
    for w in windows:
        w.pitch_mean_hz, w.pitch_std_semitones = prosody.pitch_for_span(track.times, track.f0, w.start, w.end)

    progress(0.62, "Analyzing emotional expression")
    emotion.analyze_windows(signal, windows, settings, lambda f: progress(0.62 + 0.30 * f, "Analyzing emotional expression"))

    progress(0.92, "Analyzing content tone")
    sentiment.analyze_windows(windows, lambda f: progress(0.92 + 0.05 * f, "Analyzing content tone"))

    progress(0.97, "Writing report")
    durations = {id(w): w.duration for w in windows}
    labels = sorted({label for w in windows for label in w.emotion})
    distribution = {}
    for label in labels:
        scored = [w for w in windows if label in w.emotion]
        distribution[label], _ = _weighted([w.emotion[label] for w in scored], [durations[id(w)] for w in scored])
    dims_mean, dims_std = {}, {}
    for dim in ("arousal", "dominance", "valence"):
        scored = [w for w in windows if getattr(w, dim) is not None]
        if scored:
            dims_mean[dim], dims_std[dim] = _weighted([getattr(w, dim) for w in scored], [durations[id(w)] for w in scored])
    toned = [w for w in windows if w.sentiment is not None]
    overall_sentiment = _weighted([w.sentiment for w in toned], [float(w.words) for w in toned])[0] if toned else None

    wav_path.unlink(missing_ok=True)
    return Analysis(
        file_name=file_name,
        duration=duration,
        analyzed_at=datetime.now(timezone.utc),
        transcript=transcript,
        pauses=pauses,
        rate=rate,
        fillers=fillers,
        pitch=track.pitch,
        loudness=track.loudness,
        voice_quality=track.quality,
        windows=windows,
        emotion_distribution=distribution,
        dimensions_mean=dims_mean,
        dimensions_std=dims_std,
        sentiment=overall_sentiment,
        models={
            "transcription": f"faster-whisper {settings.whisper_model} (int8, beam {settings.whisper_beam})",
            "emotion dimensions": EMOTION_DIMENSIONS_MODEL,
            "emotion categories": EMOTION_CATEGORIES_MODEL if settings.categorical_emotion else "disabled",
            "content tone": SENTIMENT_MODEL,
            "pitch / loudness / clarity": "Praat algorithms via parselmouth",
        },
    )
