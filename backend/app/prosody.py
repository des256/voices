"""Delivery and voice metrics: pauses, pace, fillers (from word timestamps) and pitch/loudness/clarity (Praat)."""

from __future__ import annotations

import string
from collections import Counter
from pathlib import Path

import numpy as np

from app.schema import FillerStats, LoudnessStats, PauseStats, PitchStats, RateStats, VoiceQuality, Word

FILLERS: dict[str, set[str]] = {
    "en": {"uh", "um", "er", "erm", "hmm", "hm", "mm", "uhm", "umm", "ah", "eh", "ehm"},
    "nl": {"eh", "ehm", "euh", "uh", "uhm", "hm", "hmm", "mm", "um", "eum", "uhm"},
    "de": {"äh", "ähm", "hm", "hmm", "mh", "öh", "öhm"},
    "fr": {"euh", "hum", "hm", "ben", "bah"},
}
_STRIP = string.punctuation + "…“”‘’«»"


def _normalize(token: str) -> str:
    return token.lower().strip(_STRIP)


def pause_stats(words: list[Word], threshold: float = 0.5) -> PauseStats:
    empty = PauseStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0)
    if len(words) < 2:
        return empty
    pauses = [(w2.start - w1.end, w1.end) for w1, w2 in zip(words, words[1:]) if w2.start - w1.end >= threshold]
    span = words[-1].end - words[0].start
    total = sum(g for g, _ in pauses)
    longest, at = max(pauses, default=(0.0, 0.0))
    return PauseStats(
        count=len(pauses),
        total_seconds=total,
        mean_seconds=total / len(pauses) if pauses else 0.0,
        longest_seconds=longest,
        longest_at=at,
        ratio=total / span if span > 0 else 0.0,
        short=sum(1 for g, _ in pauses if g < 1.0),
        medium=sum(1 for g, _ in pauses if 1.0 <= g < 2.0),
        long=sum(1 for g, _ in pauses if g >= 2.0),
    )


def rate_stats(words: list[Word], pause_seconds: float) -> RateStats:
    if not words:
        return RateStats(0, 0.0, 0.0, 0.0, 0.0, [])
    n = len(words)
    span = words[-1].end - words[0].start
    articulation = max(span - pause_seconds, 0.0)
    per_minute = [0] * (int(words[-1].start // 60) + 1)
    for w in words:
        per_minute[int(w.start // 60)] += 1
    return RateStats(
        words=n,
        speech_span_seconds=span,
        articulation_seconds=articulation,
        wpm=n / span * 60 if span > 0 else 0.0,
        articulation_wpm=n / articulation * 60 if articulation > 0 else 0.0,
        per_minute=per_minute,
    )


def filler_stats(words: list[Word], language: str, duration_seconds: float) -> FillerStats:
    vocab = FILLERS.get(language) or set().union(*FILLERS.values())
    counter = Counter(tok for tok in (_normalize(w.text) for w in words) if tok in vocab)
    total = sum(counter.values())
    per_minute = total / (duration_seconds / 60) if duration_seconds > 0 else 0.0
    return FillerStats(total=total, per_minute=per_minute, counts=dict(counter.most_common()))


def pitch_stats_from_f0(f0: np.ndarray) -> PitchStats:
    f0 = np.asarray(f0, dtype=float)
    voiced = f0[f0 > 0]
    if voiced.size == 0:
        return PitchStats(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    semitones = 12 * np.log2(voiced / 100.0)
    p5, p95 = np.percentile(voiced, [5, 95])
    return PitchStats(
        mean_hz=float(voiced.mean()),
        median_hz=float(np.median(voiced)),
        std_semitones=float(semitones.std()),
        range_semitones=float(np.percentile(semitones, 95) - np.percentile(semitones, 5)),
        p5_hz=float(p5),
        p95_hz=float(p95),
        voiced_ratio=float(voiced.size / f0.size),
    )


def pitch_for_span(times: np.ndarray, f0: np.ndarray, start: float, end: float) -> tuple[float | None, float | None]:
    mask = (times >= start) & (times < end) & (f0 > 0)
    if mask.sum() < 5:
        return None, None
    voiced = f0[mask]
    return float(voiced.mean()), float((12 * np.log2(voiced / 100.0)).std())


class AcousticTrack:
    def __init__(self, times: np.ndarray, f0: np.ndarray, pitch: PitchStats, loudness: LoudnessStats, quality: VoiceQuality):
        self.times = times
        self.f0 = f0
        self.pitch = pitch
        self.loudness = loudness
        self.quality = quality


def acoustics(wav_path: Path) -> AcousticTrack:
    """Pitch, loudness and harmonics-to-noise ratio over the whole recording using Praat algorithms."""
    import parselmouth

    snd = parselmouth.Sound(str(wav_path))
    pitch = snd.to_pitch_ac(time_step=0.01, pitch_floor=70.0, pitch_ceiling=500.0)
    f0 = np.asarray(pitch.selected_array["frequency"], dtype=float)
    times = np.asarray(pitch.xs(), dtype=float)

    intensity = snd.to_intensity(minimum_pitch=70.0, time_step=0.01)
    db = np.asarray(intensity.values[0], dtype=float)
    db = db[np.isfinite(db)]
    speech = db[db > db.max() - 35.0] if db.size else db
    if speech.size:
        loud = LoudnessStats(
            mean_db=float(speech.mean()),
            std_db=float(speech.std()),
            range_db=float(np.percentile(speech, 95) - np.percentile(speech, 5)),
        )
    else:
        loud = LoudnessStats(0.0, 0.0, 0.0)

    harmonicity = snd.to_harmonicity_cc(time_step=0.01, minimum_pitch=70.0)
    hnr = np.asarray(harmonicity.values[0], dtype=float)
    hnr = hnr[hnr > -100]  # Praat marks unvoiced frames with -200 dB
    quality = VoiceQuality(hnr_db=float(hnr.mean()) if hnr.size else 0.0)

    return AcousticTrack(times, f0, pitch_stats_from_f0(f0), loud, quality)
