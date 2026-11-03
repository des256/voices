#!/bin/bash
# Deploys Voices to voices.germansmedia.nl following ~/germansmedia/NEWSITE.md:
#   frontend  -> /srv/sites/voices   (static Flutter web build, served by Caddy)
#   backend   -> /srv/apps/voices    (built and run there with docker compose, 127.0.0.1:8080)
#   Caddy     -> /etc/caddy/sites/voices.caddy (created once if missing)
set -euo pipefail
cd "$(dirname "$0")"

NAME=voices
HOST=transip
version=$(awk '$1 == "version:" { print $2; exit }' pubspec.yaml)

read -r -p "This will build and deploy Voices ${version} to ${NAME}.germansmedia.nl. Are you sure? [y/N] " response
case "$response" in
    [yY][eE][sS]|[yY]) ;;
    *) echo "Aborted."; exit 0 ;;
esac

echo "==> Checking server prerequisites"
ssh -t "$HOST" 'test -d /srv/apps || (sudo mkdir -p /srv/apps && sudo chown "$USER:$USER" /srv/apps)'
if ! ssh "$HOST" "test -f /srv/apps/${NAME}/.env"; then
    echo "Missing /srv/apps/${NAME}/.env on the server. Create it from backend/.env.example first, e.g.:"
    echo "  ssh ${HOST} 'mkdir -p /srv/apps/${NAME}' && scp backend/.env.example ${HOST}:/srv/apps/${NAME}/.env && ssh ${HOST} nano /srv/apps/${NAME}/.env"
    exit 1
fi

echo "==> Building frontend"
flutter build web

echo "==> Uploading frontend"
rsync -az --delete --chmod=D755,F644 build/web/ "${HOST}:/srv/sites/${NAME}/"

echo "==> Uploading backend"
rsync -az --delete --exclude .git --exclude .venv --exclude data --exclude .env \
    --exclude __pycache__ --exclude .pytest_cache --exclude .ruff_cache backend/ "${HOST}:/srv/apps/${NAME}/"

echo "==> Building and starting backend container (first build downloads ~3 GB of models)"
ssh "$HOST" "cd /srv/apps/${NAME} && docker compose up -d --build"

if ! ssh "$HOST" "test -f /etc/caddy/sites/${NAME}.caddy"; then
    echo "==> Installing Caddy site file"
    ssh -t "$HOST" "sudo tee /etc/caddy/sites/${NAME}.caddy >/dev/null" < deploy/voices.caddy
    ssh -t "$HOST" 'sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && sudo systemctl reload caddy'
fi

echo "==> Checking"
curl -sI "https://${NAME}.germansmedia.nl/" | head -1
curl -s "https://${NAME}.germansmedia.nl/api/health"; echo
echo "Done. Deployed Voices ${version} to https://${NAME}.germansmedia.nl"
