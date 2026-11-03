"""Emotional expression from the voice signal.

Two wav2vec2 models run per window of speech:
* dimensional arousal / dominance / valence (audeering, trained on MSP-Podcast), each in 0..1
* categorical neutral / happy / angry / sad (SUPERB emotion recognition, trained on IEMOCAP)
"""

from __future__ import annotations

import gc
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification, Wav2Vec2FeatureExtractor, Wav2Vec2Model, Wav2Vec2PreTrainedModel

from app.audio import SAMPLE_RATE
from app.models import EMOTION_CATEGORIES_MODEL, EMOTION_DIMENSIONS_MODEL
from app.schema import Window
from app.settings import Settings

CATEGORY_NAMES = {"neu": "neutral", "hap": "happy", "ang": "angry", "sad": "sad"}
MIN_WINDOW_SECONDS = 0.5


class RegressionHead(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, features):
        x = self.dropout(features)
        x = torch.tanh(self.dense(x))
        x = self.dropout(x)
        return self.out_proj(x)


class EmotionModel(Wav2Vec2PreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.wav2vec2 = Wav2Vec2Model(config)
        self.classifier = RegressionHead(config)
        self.init_weights()

    def forward(self, input_values):
        hidden_states = self.wav2vec2(input_values)[0]
        pooled = torch.mean(hidden_states, dim=1)
        return pooled, self.classifier(pooled)


def _chunk(audio: np.ndarray, window: Window) -> np.ndarray | None:
    start, end = int(window.start * SAMPLE_RATE), int(window.end * SAMPLE_RATE)
    chunk = audio[max(start, 0):min(end, len(audio))]
    if len(chunk) < MIN_WINDOW_SECONDS * SAMPLE_RATE:
        return None
    return chunk


def _feature_extractor(model_id: str):
    try:
        return Wav2Vec2FeatureExtractor.from_pretrained(model_id)
    except Exception:  # repo without preprocessor_config.json
        return Wav2Vec2FeatureExtractor(feature_size=1, sampling_rate=SAMPLE_RATE, padding_value=0.0, do_normalize=True, return_attention_mask=True)


def analyze_dimensions(audio: np.ndarray, windows: list[Window], progress: Callable[[float], None]) -> None:
    extractor = _feature_extractor(EMOTION_DIMENSIONS_MODEL)
    model = EmotionModel.from_pretrained(EMOTION_DIMENSIONS_MODEL).eval()
    try:
        for i, window in enumerate(windows):
            chunk = _chunk(audio, window)
            if chunk is None:
                continue
            inputs = extractor(chunk, sampling_rate=SAMPLE_RATE, return_tensors="pt")
            with torch.inference_mode():
                _, logits = model(inputs["input_values"])
            arousal, dominance, valence = (float(min(max(v, 0.0), 1.0)) for v in logits[0].tolist())
            window.arousal, window.dominance, window.valence = arousal, dominance, valence
            progress((i + 1) / len(windows))
    finally:
        del model
        gc.collect()


def analyze_categories(audio: np.ndarray, windows: list[Window], progress: Callable[[float], None]) -> None:
    extractor = AutoFeatureExtractor.from_pretrained(EMOTION_CATEGORIES_MODEL)
    model = AutoModelForAudioClassification.from_pretrained(EMOTION_CATEGORIES_MODEL).eval()
    id2label = model.config.id2label
    try:
        for i, window in enumerate(windows):
            chunk = _chunk(audio, window)
            if chunk is None:
                continue
            inputs = extractor(chunk, sampling_rate=SAMPLE_RATE, return_tensors="pt")
            with torch.inference_mode():
                logits = model(**inputs).logits
            probs = torch.softmax(logits[0], dim=-1).tolist()
            window.emotion = {CATEGORY_NAMES.get(id2label[j], id2label[j]): float(p) for j, p in enumerate(probs)}
            progress((i + 1) / len(windows))
    finally:
        del model
        gc.collect()


def analyze_windows(audio: np.ndarray, windows: list[Window], settings: Settings, progress: Callable[[float], None]) -> None:
    if not windows:
        progress(1.0)
        return
    if settings.categorical_emotion:
        analyze_dimensions(audio, windows, lambda f: progress(f * 0.6))
        analyze_categories(audio, windows, lambda f: progress(0.6 + f * 0.4))
    else:
        analyze_dimensions(audio, windows, progress)
