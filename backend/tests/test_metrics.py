"""Unit tests for the pure delivery/voice metrics derived from word timestamps and F0 tracks."""

import numpy as np
import pytest

from app.prosody import filler_stats, pause_stats, pitch_stats_from_f0, rate_stats
from app.schema import Word


def words_from(spec):
    return [Word(start=s, end=e, text=t) for s, e, t in spec]


def test_pause_stats_counts_gaps_at_or_above_threshold():
    words = words_from(
        [(0.0, 0.4, "hello"), (0.5, 0.9, "there"), (2.0, 2.4, "friends"), (2.5, 2.8, "and"), (5.0, 5.3, "more")]
    )
    p = pause_stats(words, threshold=0.5)
    # gaps: 0.1 (no), 1.1 (medium), 0.1 (no), 2.2 (long)
    assert p.count == 2
    assert p.total_seconds == pytest.approx(3.3)
    assert p.mean_seconds == pytest.approx(1.65)
    assert p.longest_seconds == pytest.approx(2.2)
    assert p.longest_at == pytest.approx(2.8)
    assert p.ratio == pytest.approx(3.3 / 5.3)
    assert (p.short, p.medium, p.long) == (0, 1, 1)


def test_pause_stats_with_fewer_than_two_words_is_empty():
    p = pause_stats(words_from([(1.0, 1.5, "hi")]), threshold=0.5)
    assert p.count == 0 and p.total_seconds == 0.0 and p.longest_seconds == 0.0 and p.ratio == 0.0


def test_rate_stats_words_per_minute_and_articulation_rate():
    run1 = [(i, i + 1, f"w{i}") for i in range(5)]
    run2 = [(15 + i, 16 + i, f"v{i}") for i in range(5)]
    words = words_from(run1 + run2)
    r = rate_stats(words, pause_seconds=10.0)
    assert r.words == 10
    assert r.speech_span_seconds == pytest.approx(20.0)
    assert r.wpm == pytest.approx(30.0)
    assert r.articulation_wpm == pytest.approx(60.0)
    assert r.per_minute == [10]


def test_rate_stats_per_minute_buckets_by_word_start():
    words = words_from([(0, 1, "a"), (59.5, 60.5, "b"), (61, 62, "c"), (130, 131, "d")])
    r = rate_stats(words, pause_seconds=0.0)
    assert r.per_minute == [2, 1, 1]


def test_filler_stats_counts_language_specific_fillers_ignoring_case_and_punctuation():
    words = words_from([(0, 1, "So"), (1, 2, "uh"), (2, 3, "I"), (3, 4, "um,"), (4, 5, "think"), (5, 6, "Uh")])
    f = filler_stats(words, language="en", duration_seconds=120.0)
    assert f.total == 3
    assert f.counts == {"uh": 2, "um": 1}
    assert f.per_minute == pytest.approx(1.5)


def test_filler_stats_dutch_list_and_zero_duration():
    words = words_from([(0, 1, "Eh"), (1, 2, "ja"), (2, 3, "ehm")])
    f = filler_stats(words, language="nl", duration_seconds=0.0)
    assert f.total == 2 and f.per_minute == 0.0


def test_pitch_stats_from_f0_uses_voiced_frames_only_in_semitones():
    f0 = np.array([100.0, 0.0, 200.0, 0.0, 100.0, 200.0])
    p = pitch_stats_from_f0(f0)
    assert p.mean_hz == pytest.approx(150.0)
    assert p.median_hz == pytest.approx(150.0)
    assert p.voiced_ratio == pytest.approx(4 / 6)
    assert p.std_semitones == pytest.approx(6.0)
    assert p.range_semitones == pytest.approx(12.0)


def test_pitch_stats_from_f0_without_voiced_frames_is_zeroed():
    p = pitch_stats_from_f0(np.zeros(10))
    assert p.mean_hz == 0.0 and p.std_semitones == 0.0 and p.voiced_ratio == 0.0
