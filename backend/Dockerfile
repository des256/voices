# Voices backend: FastAPI + faster-whisper + wav2vec2 emotion models, CPU only.
# Models are downloaded at build time so the container works offline and starts instantly.
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/

WORKDIR /srv/voices
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/models \
    VOICES_DATA_DIR=/data \
    PYTHONUNBUFFERED=1

# 1. Python dependencies (cached unless pyproject/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# 2. Models (cached unless the model list or WHISPER_MODEL change)
ARG WHISPER_MODEL=small
ENV VOICES_WHISPER_MODEL=${WHISPER_MODEL}
COPY app/__init__.py app/models.py app/
RUN .venv/bin/python -m app.models

# 3. Application code
COPY app ./app
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD .venv/bin/python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3).status == 200 else 1)"
CMD [".venv/bin/uvicorn", "app.main:build", "--factory", "--host", "0.0.0.0", "--port", "8080"]
