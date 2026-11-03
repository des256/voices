from datetime import datetime, timezone

import pytest

from app.schema import (
    Analysis,
    FillerStats,
    LoudnessStats,
    PauseStats,
    PitchStats,
    RateStats,
    Segment,
    Transcript,
    VoiceQuality,
    Window,
    Word,
)


@pytest.fixture
def sample_analysis() -> Analysis:
    words = [Word(0.0, 0.4, "Hello"), Word(0.5, 0.9, "everyone,"), Word(2.0, 2.3, "um"), Word(2.4, 3.0, "welcome.")]
    segment = Segment(start=0.0, end=3.0, text="Hello everyone, um welcome.", words=words)
    transcript = Transcript(language="en", language_probability=0.98, duration=3.5, segments=[segment])
    window = Window(
        start=0.0,
        end=3.0,
        text=segment.text,
        words=4,
        emotion={"neutral": 0.6, "happy": 0.3, "angry": 0.05, "sad": 0.05},
        arousal=0.55,
        dominance=0.6,
        valence=0.7,
        sentiment=0.4,
        pitch_mean_hz=190.0,
        pitch_std_semitones=2.1,
    )
    return Analysis(
        file_name="student.mp3",
        duration=3.5,
        analyzed_at=datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc),
        transcript=transcript,
        pauses=PauseStats(count=1, total_seconds=1.1, mean_seconds=1.1, longest_seconds=1.1, longest_at=0.9, ratio=0.37, short=0, medium=1, long=0),
        rate=RateStats(words=4, speech_span_seconds=3.0, articulation_seconds=1.9, wpm=80.0, articulation_wpm=126.3, per_minute=[4]),
        fillers=FillerStats(total=1, per_minute=17.1, counts={"um": 1}),
        pitch=PitchStats(mean_hz=190.0, median_hz=188.0, std_semitones=2.1, range_semitones=7.5, p5_hz=150.0, p95_hz=230.0, voiced_ratio=0.6),
        loudness=LoudnessStats(mean_db=62.0, std_db=4.2, range_db=14.0),
        voice_quality=VoiceQuality(hnr_db=16.5),
        windows=[window],
        emotion_distribution={"neutral": 0.6, "happy": 0.3, "angry": 0.05, "sad": 0.05},
        dimensions_mean={"arousal": 0.55, "dominance": 0.6, "valence": 0.7},
        dimensions_std={"arousal": 0.0, "dominance": 0.0, "valence": 0.0},
        sentiment=0.4,
        models={"transcription": "faster-whisper small", "emotion": "test"},
    )
