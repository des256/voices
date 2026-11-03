"""Tone of the spoken content: multilingual sentiment of each window's text, mapped to -1 (negative) .. +1 (positive)."""

from __future__ import annotations

import gc
import re
from typing import Callable

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.models import SENTIMENT_MODEL
from app.schema import Window

MIN_WORDS = 3


def _stars(label: str, index: int) -> int:
    match = re.search(r"\d", label)
    return int(match.group()) if match else index + 1


def analyze_windows(windows: list[Window], progress: Callable[[float], None]) -> None:
    eligible = [w for w in windows if w.words >= MIN_WORDS and w.text.strip()]
    if not eligible:
        progress(1.0)
        return
    tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL).eval()
    stars = torch.tensor([_stars(model.config.id2label[i], i) for i in range(model.config.num_labels)], dtype=torch.float32)
    try:
        for i, window in enumerate(eligible):
            inputs = tokenizer(window.text, truncation=True, max_length=256, return_tensors="pt")
            with torch.inference_mode():
                probs = torch.softmax(model(**inputs).logits[0], dim=-1)
            expected = float((probs * stars).sum())
            window.sentiment = (expected - 3.0) / 2.0
            progress((i + 1) / len(eligible))
    finally:
        del model
        gc.collect()
