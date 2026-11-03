"""Data model shared by the analysis pipeline, the report renderer and the API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class Word:
    start: float
    end: float
    text: str
    probability: float = 1.0


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class Transcript:
    language: str
    language_probability: float
    duration: float
    segments: list[Segment]

    @property
    def words(self) -> list[Word]:
        return [w for s in self.segments for w in s.words]

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments).strip()


@dataclass
class PauseStats:
    count: int
    total_seconds: float
    mean_seconds: float
    longest_seconds: float
    longest_at: float
    ratio: float
    short: int  # threshold .. 1 s
    medium: int  # 1 .. 2 s
    long: int  # >= 2 s


@dataclass
class RateStats:
    words: int
    speech_span_seconds: float
    articulation_seconds: float
    wpm: float
    articulation_wpm: float
    per_minute: list[int]


@dataclass
class FillerStats:
    total: int
    per_minute: float
    counts: dict[str, int]


@dataclass
class PitchStats:
    mean_hz: float
    median_hz: float
    std_semitones: float
    range_semitones: float
    p5_hz: float
    p95_hz: float
    voiced_ratio: float


@dataclass
class LoudnessStats:
    mean_db: float
    std_db: float
    range_db: float


@dataclass
class VoiceQuality:
    hnr_db: float


@dataclass
class Window:
    """A few seconds of speech: the unit for emotion, tone and pitch timelines."""

    start: float
    end: float
    text: str
    words: int
    emotion: dict[str, float] = field(default_factory=dict)
    arousal: float | None = None
    dominance: float | None = None
    valence: float | None = None
    sentiment: float | None = None
    pitch_mean_hz: float | None = None
    pitch_std_semitones: float | None = None

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)

    @property
    def dominant_emotion(self) -> str | None:
        if not self.emotion:
            return None
        return max(self.emotion.items(), key=lambda kv: kv[1])[0]


@dataclass
class Analysis:
    file_name: str
    duration: float
    analyzed_at: datetime
    transcript: Transcript
    pauses: PauseStats
    rate: RateStats
    fillers: FillerStats
    pitch: PitchStats
    loudness: LoudnessStats
    voice_quality: VoiceQuality
    windows: list[Window]
    emotion_distribution: dict[str, float]
    dimensions_mean: dict[str, float]
    dimensions_std: dict[str, float]
    sentiment: float | None
    models: dict[str, str]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["analyzed_at"] = self.analyzed_at.isoformat()
        return d
