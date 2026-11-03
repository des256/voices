"""Render an Analysis as a Markdown report for the coach."""

from __future__ import annotations

import math

from app.schema import Analysis, Window

LANGUAGE_NAMES = {
    "en": "English", "nl": "Dutch", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
    "pt": "Portuguese", "pl": "Polish", "sv": "Swedish", "da": "Danish", "no": "Norwegian", "fi": "Finnish",
    "tr": "Turkish", "ar": "Arabic", "ru": "Russian", "uk": "Ukrainian", "zh": "Chinese", "ja": "Japanese",
    "ko": "Korean", "hi": "Hindi", "id": "Indonesian", "af": "Afrikaans",
}
EMOTION_LABELS = {"neutral": "Neutral", "happy": "Happy", "angry": "Angry / tense", "sad": "Sad / subdued"}


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def fmt_clock(seconds: float) -> str:
    seconds = max(0.0, seconds)
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def pct(x: float) -> str:
    return f"{round(x * 100):d}%"


def _num(x: float | None, digits: int = 0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{x:.{digits}f}"


PACE_REFERENCE = "conversational speech is 120–160 wpm"


def read_pace(wpm: float) -> str:
    if wpm <= 0:
        return "–"
    if wpm < 110:
        return "slow and deliberate"
    if wpm <= 160:
        return "comfortable conversational pace"
    if wpm <= 185:
        return "brisk"
    return "fast; listeners may struggle to follow"


def read_pauses(ratio: float, long_count: int) -> str:
    if ratio < 0.10:
        base = "few pauses; the delivery may feel rushed"
    elif ratio <= 0.25:
        base = "healthy amount of pausing"
    else:
        base = "a lot of pausing; check whether pauses are intentional"
    if long_count:
        base += f", {long_count} long pause{'s' if long_count != 1 else ''} (≥ 2 s)"
    return base


def read_fillers(per_minute: float) -> str:
    if per_minute == 0:
        return "none detected"
    if per_minute < 2:
        return "rare; barely noticeable"
    if per_minute <= 5:
        return "noticeable; worth working on"
    return "frequent; a clear focus point"


def read_pitch_variation(std_st: float) -> str:
    if std_st <= 0:
        return "–"
    if std_st < 1.5:
        return "flat / monotone"
    if std_st < 3.0:
        return "moderately expressive"
    return "lively and expressive"


def read_loudness(std_db: float) -> str:
    if std_db <= 0:
        return "–"
    if std_db < 2.0:
        return "flat dynamics"
    if std_db < 5.0:
        return "moderate dynamics"
    return "strong dynamics"


def read_hnr(hnr: float) -> str:
    if hnr <= 0:
        return "–"
    if hnr >= 12:
        return "clear, resonant voice"
    if hnr >= 7:
        return "typical for conversational speech"
    return "breathy, hoarse, or a noisy recording"


def read_dimension(name: str, value: float) -> str:
    low, high = {
        "arousal": ("calm, low energy", "energetic, animated"),
        "valence": ("negative or serious colouring", "warm, positive colouring"),
        "dominance": ("tentative, soft", "assertive, confident"),
    }[name]
    if value < 0.4:
        return low
    if value <= 0.6:
        return "balanced"
    return high


def read_sentiment(score: float | None) -> str:
    if score is None or math.isnan(score):
        return "–"
    if score < -0.5:
        return "clearly negative"
    if score < -0.15:
        return "mildly negative"
    if score <= 0.15:
        return "neutral"
    if score <= 0.5:
        return "mildly positive"
    return "clearly positive"


def _emotion_summary(dist: dict[str, float]) -> tuple[str, str]:
    if not dist:
        return "–", ""
    ordered = sorted(dist.items(), key=lambda kv: kv[1], reverse=True)
    top, rest = ordered[0], ordered[1:]
    return f"{EMOTION_LABELS.get(top[0], top[0])} {pct(top[1])}", ", ".join(f"{EMOTION_LABELS.get(k, k).lower()} {pct(v)}" for k, v in rest)


def _window_row(w: Window) -> str:
    emo = EMOTION_LABELS.get(w.dominant_emotion, w.dominant_emotion) if w.dominant_emotion else "–"
    pace = f"{w.words / w.duration * 60:.0f}" if w.duration > 0 and w.words else "–"
    return (
        f"| {fmt_clock(w.start)}–{fmt_clock(w.end)} | {emo} | {_num(w.arousal, 2)} | {_num(w.valence, 2)} | "
        f"{_num(w.dominance, 2)} | {_num(w.sentiment, 2)} | {_num(w.pitch_mean_hz)} | {pace} |"
    )


def render_markdown(a: Analysis) -> str:
    t = a.transcript
    language = LANGUAGE_NAMES.get(t.language, t.language.upper())
    has_speech = a.rate.words > 0 and bool(t.segments)
    lines: list[str] = []
    add = lines.append

    add("# Voice Analysis Report")
    add("")
    add("| | |")
    add("|---|---|")
    add(f"| **Recording** | {a.file_name} |")
    add(f"| **Duration** | {fmt_time(a.duration)} min |")
    add(f"| **Language** | {language} ({pct(t.language_probability)} confidence) |")
    add(f"| **Analyzed** | {a.analyzed_at.strftime('%Y-%m-%d %H:%M UTC')} |")
    add("")

    if not has_speech:
        add("## At a glance")
        add("")
        add("No speech was detected in this recording, so the delivery, emotion and tone sections are empty. "
            "Check that the right file was uploaded and that the voice is audible.")
        add("")
        _append_method(lines, a)
        return "\n".join(lines).rstrip() + "\n"

    top_emotion, other_emotions = _emotion_summary(a.emotion_distribution)
    dm, ds = a.dimensions_mean, a.dimensions_std

    add("## At a glance")
    add("")
    add("| Metric | Value | Reading |")
    add("|---|---|---|")
    add(f"| Speaking rate | {a.rate.wpm:.0f} wpm | {read_pace(a.rate.wpm)}; {PACE_REFERENCE} |")
    add(f"| Articulation rate | {a.rate.articulation_wpm:.0f} wpm | pace while actually speaking (pauses excluded) |")
    add(f"| Pauses | {a.pauses.count} ({pct(a.pauses.ratio)} of speaking time) | {read_pauses(a.pauses.ratio, a.pauses.long)} |")
    filler_detail = ", ".join(f"{k} ×{v}" for k, v in a.fillers.counts.items())
    filler_reading = f"{read_fillers(a.fillers.per_minute)}: {filler_detail}" if a.fillers.total else "none detected"
    add(f"| Filler words | {a.fillers.total} ({a.fillers.per_minute:.1f} per minute) | {filler_reading} |")
    add(f"| Pitch | {a.pitch.mean_hz:.0f} Hz average | variation {a.pitch.std_semitones:.1f} semitones: {read_pitch_variation(a.pitch.std_semitones)} |")
    add(f"| Pitch range | {a.pitch.range_semitones:.1f} semitones | {a.pitch.p5_hz:.0f}–{a.pitch.p95_hz:.0f} Hz (5th–95th percentile) |")
    add(f"| Loudness variation | ±{a.loudness.std_db:.1f} dB | {read_loudness(a.loudness.std_db)} (range {a.loudness.range_db:.0f} dB) |")
    add(f"| Voice clarity (HNR) | {a.voice_quality.hnr_db:.1f} dB | {read_hnr(a.voice_quality.hnr_db)} |")
    add(f"| Dominant emotion (voice) | {top_emotion} | {other_emotions} |")
    if "arousal" in dm:
        add(f"| Energy (arousal) | {dm['arousal']:.2f} / 1 | {read_dimension('arousal', dm['arousal'])}, variability ±{ds['arousal']:.2f} |")
        add(f"| Positivity (valence) | {dm['valence']:.2f} / 1 | {read_dimension('valence', dm['valence'])}, variability ±{ds['valence']:.2f} |")
        add(f"| Assertiveness (dominance) | {dm['dominance']:.2f} / 1 | {read_dimension('dominance', dm['dominance'])}, variability ±{ds['dominance']:.2f} |")
    add(f"| Content tone | {_num(a.sentiment, 2)} (−1 … +1) | {read_sentiment(a.sentiment)} |")
    add("")

    add("## Delivery: pace, pauses and fillers")
    add("")
    add(f"The student spoke **{a.rate.words} words** between {fmt_clock(t.words[0].start)} and {fmt_clock(t.words[-1].end)}, "
        f"an overall rate of **{a.rate.wpm:.0f} words per minute**: {read_pace(a.rate.wpm)} ({PACE_REFERENCE}). "
        f"Excluding pauses, the articulation rate was **{a.rate.articulation_wpm:.0f} wpm**.")
    add("")
    if len(a.rate.per_minute) > 1:
        add("| Minute | Words |")
        add("|---|---|")
        for i, n in enumerate(a.rate.per_minute):
            add(f"| {i + 1} | {n} |")
        add("")
    add(f"**Pauses** (silences of at least 0.5 s between words): {a.pauses.count} in total, "
        f"covering {a.pauses.total_seconds:.1f} s ({pct(a.pauses.ratio)} of the speaking time). "
        f"Short (0.5–1 s): {a.pauses.short}, medium (1–2 s): {a.pauses.medium}, long (≥ 2 s): {a.pauses.long}. ")
    if a.pauses.count:
        add(f"The longest pause lasted {a.pauses.longest_seconds:.1f} s at {fmt_clock(a.pauses.longest_at)}.")
    add("")
    if a.fillers.total:
        add(f"**Filler words**: {a.fillers.total} ({a.fillers.per_minute:.1f} per minute, {read_fillers(a.fillers.per_minute)}): {filler_detail}. "
            "Automatic transcription tends to drop some fillers, so treat this as a lower bound.")
    else:
        add("**Filler words**: none were detected. Automatic transcription tends to drop some fillers, so listen for them anyway.")
    add("")

    add("## Voice: pitch, loudness and clarity")
    add("")
    add(f"**Pitch** averaged {a.pitch.mean_hz:.0f} Hz (median {a.pitch.median_hz:.0f} Hz) and moved within "
        f"{a.pitch.p5_hz:.0f}–{a.pitch.p95_hz:.0f} Hz, a range of {a.pitch.range_semitones:.1f} semitones. "
        f"The moment-to-moment variation of {a.pitch.std_semitones:.1f} semitones reads as **{read_pitch_variation(a.pitch.std_semitones)}**. "
        f"Voiced sound (vowels and voiced consonants) made up {pct(a.pitch.voiced_ratio)} of the whole recording, silence included.")
    add("")
    add(f"**Loudness** varied by ±{a.loudness.std_db:.1f} dB around its mean, with a 5th–95th percentile range of "
        f"{a.loudness.range_db:.0f} dB: **{read_loudness(a.loudness.std_db)}**.")
    add("")
    add(f"**Clarity**: the harmonics-to-noise ratio was {a.voice_quality.hnr_db:.1f} dB, which suggests a **{read_hnr(a.voice_quality.hnr_db)}**. "
        "Background noise and microphone quality affect this number.")
    add("")

    add("## Emotional expression")
    add("")
    if a.emotion_distribution:
        add("Share of the speaking time (weighted by duration) in which each emotion dominated the voice:")
        add("")
        add("| Emotion | Share |")
        add("|---|---|")
        for k, v in sorted(a.emotion_distribution.items(), key=lambda kv: kv[1], reverse=True):
            add(f"| {EMOTION_LABELS.get(k, k)} | {pct(v)} |")
        add("")
    if dm:
        add("Dimensional ratings of the voice (0 = low, 1 = high; variability shows how much it changed during the talk):")
        add("")
        add("| Dimension | Average | Variability | Reading |")
        add("|---|---|---|---|")
        add(f"| Energy (arousal) | {dm['arousal']:.2f} | ±{ds['arousal']:.2f} | {read_dimension('arousal', dm['arousal'])} |")
        add(f"| Positivity (valence) | {dm['valence']:.2f} | ±{ds['valence']:.2f} | {read_dimension('valence', dm['valence'])} |")
        add(f"| Assertiveness (dominance) | {dm['dominance']:.2f} | ±{ds['dominance']:.2f} | {read_dimension('dominance', dm['dominance'])} |")
        add("")
    if a.windows:
        add("### Timeline")
        add("")
        add("| Time | Emotion | Energy | Positivity | Assertiveness | Tone | Pitch (Hz) | Pace (wpm) |")
        add("|---|---|---|---|---|---|---|---|")
        for w in a.windows:
            add(_window_row(w))
        add("")

    add("## Content tone")
    add("")
    add(f"The words themselves read as **{read_sentiment(a.sentiment)}** (score {_num(a.sentiment, 2)} on a scale from −1 to +1), "
        "based on a multilingual sentiment model applied to each passage of the transcript. "
        "Compare this with the voice emotion above: a positive text delivered with a flat or tense voice is a classic coaching point.")
    add("")

    add("## Transcript")
    add("")
    for seg in t.segments:
        add(f"[{fmt_clock(seg.start)}] {seg.text.strip()}")
        add("")

    _append_method(lines, a)
    return "\n".join(lines).rstrip() + "\n"


def _append_method(lines: list[str], a: Analysis) -> None:
    add = lines.append
    add("## How this report was made")
    add("")
    for k, v in a.models.items():
        add(f"- {k.capitalize()}: {v}")
    add("")
    add("Readings such as *monotone* or *comfortable pace* are indicative thresholds, not clinical measurements. "
        "Emotion models were trained on English speech and judge the sound of the voice, not the meaning of the words; "
        "results for other languages are approximate. The four-category model tends to label loud, energetic delivery as "
        "*angry / tense*, so read it together with the energy, positivity and assertiveness ratings. "
        "Transcription is automatic and may contain errors.")
