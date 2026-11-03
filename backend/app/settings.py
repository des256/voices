"""Runtime configuration, read from VOICES_* environment variables."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def default_threads() -> int:
    return max(1, min(os.cpu_count() or 2, 8))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    username: str = "coach"
    password: str | None = None
    secret: str = field(default_factory=lambda: secrets.token_hex(32))
    data_dir: Path = BACKEND_DIR / "data"
    web_dir: Path | None = None
    max_minutes: float = 60.0
    max_upload_mb: int = 300
    session_hours: int = 24 * 7
    login_delay: float = 1.0
    whisper_model: str = "small"
    whisper_beam: int = 5
    threads: int = field(default_factory=default_threads)
    categorical_emotion: bool = True
    pause_threshold: float = 0.5

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        web_dir_raw = env.get("VOICES_WEB_DIR")
        if web_dir_raw:
            web_dir: Path | None = Path(web_dir_raw)
        else:
            candidate = BACKEND_DIR.parent / "build" / "web"
            web_dir = candidate if candidate.is_dir() else None
        kwargs: dict = dict(
            username=env.get("VOICES_USERNAME", "coach"),
            password=env.get("VOICES_PASSWORD") or None,
            data_dir=Path(env.get("VOICES_DATA_DIR", str(BACKEND_DIR / "data"))),
            web_dir=web_dir,
            max_minutes=float(env.get("VOICES_MAX_MINUTES", "60")),
            max_upload_mb=int(env.get("VOICES_MAX_UPLOAD_MB", "300")),
            session_hours=int(env.get("VOICES_SESSION_HOURS", str(24 * 7))),
            login_delay=float(env.get("VOICES_LOGIN_DELAY", "1.0")),
            whisper_model=env.get("VOICES_WHISPER_MODEL", "small"),
            whisper_beam=int(env.get("VOICES_WHISPER_BEAM", "5")),
            threads=int(env.get("VOICES_THREADS", str(default_threads()))),
            categorical_emotion=_env_bool("VOICES_EMOTION_CATEGORICAL", True),
            pause_threshold=float(env.get("VOICES_PAUSE_THRESHOLD", "0.5")),
        )
        if env.get("VOICES_SECRET"):
            kwargs["secret"] = env["VOICES_SECRET"]
        return cls(**kwargs)
