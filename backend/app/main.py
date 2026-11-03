"""HTTP API for the Voices web app. All routes live under /api so Caddy can proxy them next to the static frontend."""

from __future__ import annotations

import asyncio
import hmac
import logging
import re
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import audio as audio_mod
from app.auth import COOKIE_NAME, make_token, verify_token
from app.jobs import Analyzer, JobManager
from app.settings import Settings

log = logging.getLogger("voices")
Prober = Callable[[Path], audio_mod.AudioInfo]

_EXT_RE = re.compile(r"^[a-z0-9]{1,5}$")
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class LoginBody(BaseModel):
    username: str
    password: str


def _extension(file_name: str) -> str:
    suffix = Path(file_name or "").suffix.lstrip(".").lower()
    return suffix if _EXT_RE.match(suffix) else "bin"


def _is_https(request: Request) -> bool:
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


def create_app(settings: Settings, analyzer: Analyzer | None = None, prober: Prober | None = None) -> FastAPI:
    if analyzer is None:
        from app.pipeline import analyze as analyzer
    prober = prober or audio_mod.probe
    manager = JobManager(settings, analyzer)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if not settings.password:
            log.warning("VOICES_PASSWORD is not set: nobody can log in")
        manager.start()
        yield
        manager.stop()

    app = FastAPI(title="Voices API", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    def require_session(request: Request) -> None:
        if not verify_token(settings.secret, request.cookies.get(COOKIE_NAME), now=time.time()):
            raise HTTPException(status_code=401, detail="Not signed in")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/login", status_code=204)
    async def login(body: LoginBody, request: Request, response: Response) -> Response:
        if not settings.password:
            raise HTTPException(status_code=503, detail="Login is not configured on the server")
        user_ok = hmac.compare_digest(body.username.encode(), settings.username.encode())
        pass_ok = hmac.compare_digest(body.password.encode(), settings.password.encode())
        if not (user_ok and pass_ok):
            await asyncio.sleep(settings.login_delay)
            raise HTTPException(status_code=401, detail="Wrong username or password")
        max_age = settings.session_hours * 3600
        response.set_cookie(
            COOKIE_NAME,
            make_token(settings.secret, expires_at=int(time.time()) + max_age),
            max_age=max_age,
            httponly=True,
            samesite="lax",
            secure=_is_https(request),
            path="/api",
        )
        response.status_code = 204
        return response

    @app.post("/api/logout", status_code=204)
    def logout(response: Response) -> Response:
        response.delete_cookie(COOKIE_NAME, path="/api")
        response.status_code = 204
        return response

    @app.get("/api/session", dependencies=[Depends(require_session)])
    def session() -> dict:
        return {"username": settings.username}

    @app.post("/api/jobs", status_code=202, dependencies=[Depends(require_session)])
    async def create_job(file: UploadFile = File(...)) -> dict:
        file_name = Path(file.filename or "recording").name or "recording"
        job_id, job_dir = manager.new_job_dir()
        target = job_dir / f"input.{_extension(file_name)}"
        limit = settings.max_upload_mb * 1024 * 1024
        written = 0
        try:
            with target.open("wb") as out:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > limit:
                        raise HTTPException(status_code=413, detail=f"File is larger than {settings.max_upload_mb} MB")
                    out.write(chunk)
            try:
                info = await asyncio.to_thread(prober, target)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if info.duration > settings.max_minutes * 60:
                raise HTTPException(status_code=413, detail=f"Recording is longer than {settings.max_minutes:g} minutes")
        except Exception:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise
        return manager.submit(job_id, file_name, info.duration).to_dict()

    @app.get("/api/jobs/{job_id}", dependencies=[Depends(require_session)])
    def get_job(job_id: str) -> dict:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown job")
        return job.to_dict()

    @app.get("/api/jobs/{job_id}/report", dependencies=[Depends(require_session)])
    def get_report(job_id: str, download: int = 0) -> Response:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown job")
        if job.status != "done":
            raise HTTPException(status_code=409, detail=f"Report is not ready (status: {job.status})")
        path = manager.report_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Report file is missing")
        headers = {}
        if download:
            stem = _UNSAFE_FILENAME.sub("-", Path(job.file_name).stem).strip("-") or "recording"
            headers["Content-Disposition"] = f'attachment; filename="voices-report-{stem}.md"'
        return PlainTextResponse(path.read_text(), media_type="text/markdown; charset=utf-8", headers=headers)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    if settings.web_dir and Path(settings.web_dir).is_dir():
        app.mount("/", StaticFiles(directory=str(settings.web_dir), html=True), name="web")
        log.info("serving frontend from %s", settings.web_dir)

    return app


def build() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return create_app(Settings.from_env())
