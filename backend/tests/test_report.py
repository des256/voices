from app.report import render_markdown


def test_render_markdown_contains_summary_metrics_transcript_and_method(sample_analysis):
    md = render_markdown(sample_analysis)
    assert md.startswith("# Voice Analysis Report")
    assert "student.mp3" in md
    assert "English" in md
    assert "| Speaking rate | 80 wpm" in md
    assert "| Filler words | 1" in md
    assert "um" in md
    assert "Neutral" in md and "60%" in md
    assert "[0:00] Hello everyone, um welcome." in md
    assert "faster-whisper small" in md


def test_render_markdown_handles_recording_without_speech(sample_analysis):
    sample_analysis.transcript.segments = []
    sample_analysis.windows = []
    sample_analysis.rate.words = 0
    md = render_markdown(sample_analysis)
    assert "No speech was detected" in md
