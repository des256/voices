"""Speech-to-text with word timestamps using faster-whisper (CTranslate2, int8 on CPU)."""

from __future__ import annotations

import gc
from typing import Callable

import numpy as np

from app.schema import Segment, Transcript, Word
from app.settings import Settings

# Nudges Whisper to keep disfluencies in the transcript instead of cleaning them up.
FILLER_PROMPTS = {
    "en": "Um, uh, so, like, you know, I mean, hmm... okay.",
    "nl": "Eh, ehm, uh, uhm, euh, nou, dus, zeg maar... oké.",
    "de": "Äh, ähm, also, hm, genau... okay.",
    "fr": "Euh, hum, ben, bah, donc... d'accord.",
}


def transcribe(audio: np.ndarray, duration: float, settings: Settings, progress: Callable[[float], None]) -> Transcript:
    from faster_whisper import WhisperModel

    model = WhisperModel(
        settings.whisper_model,
        device="cpu",
        compute_type="int8",
        cpu_threads=settings.threads,
        num_workers=1,
    )
    try:
        language, language_probability, _ = model.detect_language(audio, vad_filter=True)
        segments_iter, _info = model.transcribe(
            audio,
            language=language,
            beam_size=settings.whisper_beam,
            word_timestamps=True,
            vad_filter=True,
            initial_prompt=FILLER_PROMPTS.get(language),
            condition_on_previous_text=False,
        )
        segments: list[Segment] = []
        for seg in segments_iter:
            words = [
                Word(start=float(w.start), end=float(w.end), text=w.word.strip(), probability=float(w.probability))
                for w in (seg.words or [])
                if w.word.strip()
            ]
            text = seg.text.strip()
            if not text:
                continue
            segments.append(Segment(start=float(seg.start), end=float(seg.end), text=text, words=words))
            if duration > 0:
                progress(min(float(seg.end) / duration, 1.0))
    finally:
        del model
        gc.collect()
    progress(1.0)
    return Transcript(language=language, language_probability=float(language_probability), duration=duration, segments=segments)
