"""Model identifiers and a build-time downloader so the Docker image ships with every model baked in."""

from __future__ import annotations

import os

WHISPER_DEFAULT = "small"
EMOTION_DIMENSIONS_MODEL = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
EMOTION_CATEGORIES_MODEL = "superb/wav2vec2-base-superb-er"
SENTIMENT_MODEL = "nlptown/bert-base-multilingual-uncased-sentiment"

_COMMON_PATTERNS = ["*.json", "*.txt", "*.model", "vocab*", "merges.txt", "tokenizer*"]


def _weight_patterns(repo: str) -> list[str]:
    """Prefer safetensors; fall back to the PyTorch pickle only when a repo has nothing else."""
    from huggingface_hub import list_repo_files

    files = list_repo_files(repo)
    weights = "*.safetensors" if any(f.endswith(".safetensors") for f in files) else "pytorch_model.bin"
    return _COMMON_PATTERNS + [weights]


def download_all(whisper_model: str | None = None) -> None:
    from faster_whisper import download_model
    from huggingface_hub import snapshot_download

    whisper_model = whisper_model or os.environ.get("VOICES_WHISPER_MODEL", WHISPER_DEFAULT)
    print(f"downloading faster-whisper '{whisper_model}'", flush=True)
    download_model(whisper_model)
    for repo in (EMOTION_DIMENSIONS_MODEL, EMOTION_CATEGORIES_MODEL, SENTIMENT_MODEL):
        print(f"downloading {repo}", flush=True)
        snapshot_download(repo, allow_patterns=_weight_patterns(repo))
    print("all models downloaded", flush=True)


if __name__ == "__main__":
    download_all()
