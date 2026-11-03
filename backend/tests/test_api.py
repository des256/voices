"""API tests: login gate, job lifecycle, report download. The analyzer and audio probing are faked."""

import time

import pytest
from fastapi.testclient import TestClient

from app.audio import AudioInfo
from app.main import create_app
from app.settings import Settings


def fake_analyzer(sample_analysis):
    def analyze(path, file_name, progress, settings):
        progress(0.5, "Halfway")
        return sample_analysis

    return analyze


def fake_prober(path):
    return AudioInfo(duration=3.5, codec="mp3")


@pytest.fixture
def settings(tmp_path):
    return Settings(
        username="coach",
        password="secret-pass",
        secret="unit-test-secret",
        data_dir=tmp_path / "data",
        web_dir=None,
        max_minutes=60,
    )


@pytest.fixture
def client(settings, sample_analysis):
    app = create_app(settings, analyzer=fake_analyzer(sample_analysis), prober=fake_prober)
    with TestClient(app) as c:
        yield c


def login(client, password="secret-pass"):
    return client.post("/api/login", json={"username": "coach", "password": password})


def wait_done(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_endpoints_require_login(client):
    assert client.get("/api/session").status_code == 401
    assert client.post("/api/jobs", files={"file": ("a.mp3", b"x", "audio/mpeg")}).status_code == 401
    assert client.get("/api/jobs/nope").status_code == 401


def test_login_rejects_wrong_password_and_accepts_right_one(client):
    assert login(client, "wrong").status_code == 401
    assert login(client).status_code == 204
    assert client.get("/api/session").status_code == 200
    assert client.post("/api/logout").status_code == 204
    assert client.get("/api/session").status_code == 401


def test_job_lifecycle_and_report_download(client):
    login(client)
    r = client.post("/api/jobs", files={"file": ("student.mp3", b"fake-bytes", "audio/mpeg")})
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]

    body = wait_done(client, job_id)
    assert body["status"] == "done"
    assert body["progress"] == 1.0
    assert body["file_name"] == "student.mp3"

    rep = client.get(f"/api/jobs/{job_id}/report")
    assert rep.status_code == 200
    assert rep.headers["content-type"].startswith("text/markdown")
    assert rep.text.startswith("# Voice Analysis Report")

    dl = client.get(f"/api/jobs/{job_id}/report", params={"download": 1})
    assert dl.headers["content-disposition"].startswith("attachment;")
    assert ".md" in dl.headers["content-disposition"]


def test_job_report_before_done_and_unknown_job(client):
    login(client)
    assert client.get("/api/jobs/does-not-exist").status_code == 404
    assert client.get("/api/jobs/does-not-exist/report").status_code == 404


def test_upload_rejects_undecodable_audio(settings, sample_analysis):
    def bad_prober(path):
        raise ValueError("not audio")

    app = create_app(settings, analyzer=fake_analyzer(sample_analysis), prober=bad_prober)
    with TestClient(app) as c:
        login(c)
        r = c.post("/api/jobs", files={"file": ("notes.txt", b"hello", "text/plain")})
        assert r.status_code == 400
        assert "not audio" in r.json()["detail"]


def test_upload_rejects_recordings_longer_than_limit(settings, sample_analysis):
    def long_prober(path):
        return AudioInfo(duration=61 * 60, codec="wav")

    app = create_app(settings, analyzer=fake_analyzer(sample_analysis), prober=long_prober)
    with TestClient(app) as c:
        login(c)
        r = c.post("/api/jobs", files={"file": ("long.wav", b"x", "audio/wav")})
        assert r.status_code == 413


def test_finished_jobs_survive_restart(settings, sample_analysis):
    app = create_app(settings, analyzer=fake_analyzer(sample_analysis), prober=fake_prober)
    with TestClient(app) as c:
        login(c)
        job_id = c.post("/api/jobs", files={"file": ("s.mp3", b"x", "audio/mpeg")}).json()["id"]
        wait_done(c, job_id)
        assert not (settings.data_dir / "jobs" / job_id / "input.mp3").exists(), "audio should be deleted after analysis"

    app2 = create_app(settings, analyzer=fake_analyzer(sample_analysis), prober=fake_prober)
    with TestClient(app2) as c2:
        login(c2)
        assert c2.get(f"/api/jobs/{job_id}").json()["status"] == "done"
        assert c2.get(f"/api/jobs/{job_id}/report").status_code == 200


def test_analyzer_failure_is_reported_as_job_error(settings):
    def boom(path, file_name, progress, settings):
        raise RuntimeError("model exploded")

    app = create_app(settings, analyzer=boom, prober=fake_prober)
    with TestClient(app) as c:
        login(c)
        job_id = c.post("/api/jobs", files={"file": ("s.mp3", b"x", "audio/mpeg")}).json()["id"]
        body = wait_done(c, job_id)
        assert body["status"] == "error"
        assert "model exploded" in body["error"]
        assert c.get(f"/api/jobs/{job_id}/report").status_code == 409
