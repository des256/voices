# Voices

Voice analysis web app for a storytelling and speech coach, hosted at
`voices.germansmedia.nl`. Upload a recording of a student, watch the progress
bar, read the report in the browser and download it as Markdown.

The report covers:

- transcript with timestamps (language detected automatically)
- speaking rate, articulation rate, words per minute over time
- pauses (count, share of speaking time, longest pause)
- filler words (uh, um, eh, ehm, ...)
- pitch: average, range and variation (monotone vs. expressive)
- loudness dynamics and voice clarity (harmonics-to-noise ratio)
- emotional expression of the voice: neutral / happy / angry / sad shares plus
  energy (arousal), positivity (valence) and assertiveness (dominance), with a timeline
- tone of the spoken content (multilingual text sentiment)

## Architecture

```
voices.germansmedia.nl
├── /            static Flutter web build   (this repo root, served by Caddy from /srv/sites/voices)
└── /api/*       FastAPI backend in Docker   (backend/, 127.0.0.1:8080 on the VPS)
```

Backend stages run sequentially on CPU, each model is released afterwards, so a job
fits in the 3 GB VPS:

| Stage | Model / tool |
|---|---|
| Transcription + word timestamps | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) `small`, int8 |
| Emotion dimensions (arousal, dominance, valence) | `audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim` |
| Emotion categories (neutral, happy, angry, sad) | `superb/wav2vec2-base-superb-er` |
| Content tone | `nlptown/bert-base-multilingual-uncased-sentiment` |
| Pitch, loudness, HNR, pauses, pace, fillers | Praat via `parselmouth` + whisper word timestamps |

Login is a single fixed user (`VOICES_USERNAME` / `VOICES_PASSWORD`) with a signed
HttpOnly session cookie. Uploaded audio is deleted after analysis; the report and raw
analysis JSON are kept under the data volume.

### API

All routes are under `/api`:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | liveness (no auth) |
| `POST` | `/api/login` | `{username, password}`, sets the session cookie |
| `POST` | `/api/logout` | clears the cookie |
| `GET` | `/api/session` | 200 when signed in |
| `POST` | `/api/jobs` | multipart `file`, returns `202 {id, status, progress, stage, ...}` |
| `GET` | `/api/jobs/{id}` | poll status; `status` is `queued`, `running`, `done` or `error` |
| `GET` | `/api/jobs/{id}/report` | Markdown report; `?download=1` adds a `Content-Disposition` header |

## Local development

Backend (Python 3.12, [uv](https://docs.astral.sh/uv/), ffmpeg):

```bash
cd backend
uv sync
uv run python -m app.models            # one-time model download (~2 GB)
uv run pytest                          # unit + API tests
uv run pytest -m integration           # real models on a synthesized clip (needs espeak-ng)
uv run python -m app.cli recording.mp3 --out report.md   # analyze one file from the shell
```

Frontend (Flutter 3.27, web):

```bash
flutter pub get
flutter test
flutter build web
```

Run the whole app on one origin (the backend serves `build/web` when it exists):

```bash
cd backend
VOICES_PASSWORD=dev-pass uv run uvicorn app.main:build --factory --port 8080
# open http://localhost:8080
```

If ROS or another tool sets `PYTHONPATH`, prefix commands with `env -u PYTHONPATH`.

Run the production container locally, serving the frontend from a bind mount:

```bash
cd backend && docker build -t voices-backend .
docker run --rm -p 127.0.0.1:8080:8080 -e VOICES_PASSWORD=dev-pass \
  -v "$PWD/../build/web:/web:ro" -e VOICES_WEB_DIR=/web voices-backend
```

## Configuration

Environment variables read by the backend (see `backend/.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `VOICES_USERNAME` | `coach` | login name |
| `VOICES_PASSWORD` | unset | login password; login is disabled until set |
| `VOICES_SECRET` | random per start | session signing key; set it so restarts keep users signed in |
| `VOICES_DATA_DIR` | `backend/data` (`/data` in Docker) | jobs, reports |
| `VOICES_WEB_DIR` | `../build/web` if present | static frontend to serve at `/` (not used behind Caddy) |
| `VOICES_WHISPER_MODEL` | `small` | faster-whisper size; Docker build arg `WHISPER_MODEL` bakes it into the image |
| `VOICES_WHISPER_BEAM` | `5` | beam size; `1` is about twice as fast |
| `VOICES_THREADS` | CPU count (max 8) | CPU threads for inference |
| `VOICES_EMOTION_CATEGORICAL` | `true` | run the neutral/happy/angry/sad model as well |
| `VOICES_MAX_MINUTES` | `60` | reject longer recordings |
| `VOICES_MAX_UPLOAD_MB` | `300` | reject larger uploads |
| `VOICES_SESSION_HOURS` | `168` | cookie lifetime |
| `VOICES_PAUSE_THRESHOLD` | `0.5` | seconds of silence between words that count as a pause |

## Deployment

Follows `~/germansmedia/NEWSITE.md`. One-time, on the VPS:

```bash
ssh transip 'sudo mkdir -p /srv/apps && sudo chown $USER:$USER /srv/apps && mkdir -p /srv/apps/voices'
scp backend/.env.example transip:/srv/apps/voices/.env
ssh transip nano /srv/apps/voices/.env      # set VOICES_PASSWORD and VOICES_SECRET
```

Then, for every release:

```bash
./deploy.sh
```

The script builds the Flutter web app, rsyncs it to `/srv/sites/voices/`, rsyncs
`backend/` to `/srv/apps/voices/` (keeping the server-side `.env`), runs
`docker compose up -d --build` there, and installs `deploy/voices.caddy` into
`/etc/caddy/sites/` the first time. The first build downloads about 2 GB of models.

The VPS has 2 vCPUs and 3 GB RAM, so expect roughly real-time processing: a
five-minute recording takes a few minutes. The progress bar reports each stage.
