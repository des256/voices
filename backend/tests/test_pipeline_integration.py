"""Runs the real models end to end on a synthetic speech clip. Opt in with: pytest -m integration"""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.pipeline import analyze
from app.report import render_markdown
from app.settings import Settings

pytestmark = pytest.mark.integration

TEXT = (
    "Good morning everyone. Today I want to tell you a story about my grandmother. "
    "She lived in a small village near the sea, and every summer we visited her. "
    "Um, the thing I remember most is the smell of fresh bread in the morning. "
    "It was wonderful, and I still think about it every day."
)


@pytest.fixture(scope="module")
def speech_wav(tmp_path_factory) -> Path:
    if shutil.which("espeak-ng") is None or shutil.which("ffmpeg") is None:
        pytest.skip("espeak-ng and ffmpeg are required to synthesize the test clip")
    path = tmp_path_factory.mktemp("audio") / "input.wav"
    subprocess.run(["espeak-ng", "-v", "en-us", "-s", "150", "-g", "8", "-w", str(path), TEXT], check=True)
    return path


def test_pipeline_produces_transcript_metrics_and_report(speech_wav, tmp_path):
    src = tmp_path / "input.wav"
    shutil.copy(speech_wav, src)
    settings = Settings(password="x", data_dir=tmp_path, whisper_beam=2, threads=4)
    events: list[tuple[float, str]] = []

    analysis = analyze(src, "grandmother.wav", lambda f, s: events.append((f, s)), settings)

    assert analysis.transcript.language == "en"
    assert analysis.rate.words >= 30
    assert "grandmother" in analysis.transcript.text.lower()
    assert analysis.rate.wpm > 60
    assert analysis.pitch.mean_hz > 50
    assert set(analysis.dimensions_mean) == {"arousal", "dominance", "valence"}
    assert set(analysis.emotion_distribution) == {"neutral", "happy", "angry", "sad"}
    assert analysis.sentiment is not None
    assert all(0 <= w.arousal <= 1 for w in analysis.windows if w.arousal is not None)

    fractions = [f for f, _ in events]
    assert fractions == sorted(fractions), "progress must never go backwards"
    assert fractions[-1] >= 0.97
    assert {s for _, s in events} >= {"Transcribing", "Analyzing emotional expression", "Analyzing content tone", "Writing report"}

    md = render_markdown(analysis)
    assert "## Transcript" in md and "## Emotional expression" in md
    assert not (tmp_path / "audio16k.wav").exists()
