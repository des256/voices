"""Job queue: one background worker analyses uploads sequentially and persists results under the data directory."""

from __future__ import annotations

import json
import logging
import queue
import re
import shutil
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.report import render_markdown
from app.schema import Analysis
from app.settings import Settings

log = logging.getLogger("voices.jobs")

Analyzer = Callable[[Path, str, Callable[[float, str], None], Settings], Analysis]
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")


@dataclass
class Job:
    id: str
    file_name: str
    created_at: str
    duration: float
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    stage: str = "Queued"
    error: str | None = None
    finished_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class JobManager:
    def __init__(self, settings: Settings, analyzer: Analyzer):
        self.settings = settings
        self.analyzer = analyzer
        self.root = Path(settings.data_dir) / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self.queue: queue.Queue[str | None] = queue.Queue()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._worker, name="voices-worker", daemon=True)
        self._load_existing()

    # -- lifecycle -----------------------------------------------------------------
    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.queue.put(None)
        self.thread.join(timeout=2.0)

    # -- public API ----------------------------------------------------------------
    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def new_job_dir(self) -> tuple[str, Path]:
        job_id = uuid.uuid4().hex[:12]
        d = self.job_dir(job_id)
        d.mkdir(parents=True, exist_ok=False)
        return job_id, d

    def submit(self, job_id: str, file_name: str, duration: float) -> Job:
        job = Job(id=job_id, file_name=file_name, created_at=datetime.now(timezone.utc).isoformat(), duration=duration)
        with self.lock:
            self.jobs[job_id] = job
        self._persist(job)
        self.queue.put(job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        if not JOB_ID_RE.match(job_id or ""):
            return None
        with self.lock:
            return self.jobs.get(job_id)

    def report_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "report.md"

    def discard(self, job_id: str) -> None:
        shutil.rmtree(self.job_dir(job_id), ignore_errors=True)

    # -- internals -----------------------------------------------------------------
    def _input_path(self, job_id: str) -> Path | None:
        return next(self.job_dir(job_id).glob("input.*"), None)

    def _persist(self, job: Job) -> None:
        d = self.job_dir(job.id)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "job.json.tmp"
        tmp.write_text(json.dumps(job.to_dict(), indent=2))
        tmp.replace(d / "job.json")

    def _load_existing(self) -> None:
        for job_file in sorted(self.root.glob("*/job.json")):
            try:
                job = Job(**json.loads(job_file.read_text()))
            except Exception:  # corrupt entry: skip, do not crash the service
                log.warning("skipping unreadable job file %s", job_file)
                continue
            if job.status in ("queued", "running"):
                if self._input_path(job.id) is not None:
                    job.status, job.progress, job.stage = "queued", 0.0, "Queued"
                    self.queue.put(job.id)
                else:
                    job.status, job.error = "error", "Interrupted by a server restart; please upload again."
                self._persist(job)
            self.jobs[job.id] = job

    def _worker(self) -> None:
        while True:
            job_id = self.queue.get()
            if job_id is None:
                return
            job = self.get(job_id)
            if job is not None:
                self._run(job)

    def _run(self, job: Job) -> None:
        input_path = self._input_path(job.id)
        last_persist = 0.0

        def progress(fraction: float, stage: str) -> None:
            nonlocal last_persist
            job.progress = round(min(max(fraction, 0.0), 1.0), 3)
            job.stage = stage
            now = time.monotonic()
            if now - last_persist > 2.0:
                last_persist = now
                self._persist(job)

        job.status, job.stage = "running", "Starting"
        self._persist(job)
        started = time.monotonic()
        try:
            if input_path is None:
                raise FileNotFoundError("uploaded audio is missing")
            analysis = self.analyzer(input_path, job.file_name, progress, self.settings)
            d = self.job_dir(job.id)
            (d / "analysis.json").write_text(json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False))
            (d / "report.md").write_text(render_markdown(analysis))
            job.status, job.progress, job.stage = "done", 1.0, "Done"
            log.info("job %s done in %.1fs", job.id, time.monotonic() - started)
        except Exception as exc:  # report every failure to the user instead of hanging the job
            log.error("job %s failed: %s\n%s", job.id, exc, traceback.format_exc())
            job.status, job.stage, job.error = "error", "Failed", f"{type(exc).__name__}: {exc}"
        finally:
            job.finished_at = datetime.now(timezone.utc).isoformat()
            if input_path is not None:
                input_path.unlink(missing_ok=True)
            self._persist(job)
