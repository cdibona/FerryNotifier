#!/usr/bin/env bash
#
# Update FerryNotifier to the latest image WITHOUT losing saved settings.
#
# Settings (targets, keys, schedules, capture history) live in a host directory
# that is bind-mounted into the container, so recreating the container keeps them.
# Always update with THIS script (or `docker compose ... up -d`) so the mount is
# never forgotten.
#
# Override defaults via env vars, e.g.:
#   FERRY_DATA=/opt/ferry-data FERRY_PORT=8080 ./update.sh
#
set -euo pipefail

IMAGE="${FERRY_IMAGE:-ghcr.io/cdibona/ferrynotifier:latest}"
NAME="${FERRY_NAME:-ferrynotifier}"
DATA="${FERRY_DATA:-$HOME/.ferrynotifier}"      # persistent host dir for /app/data
PORT="${FERRY_PORT:-5050}"
ENVFILE="${FERRY_ENV:-.env}"

mkdir -p "$DATA"

echo "==> Pulling $IMAGE"
docker pull "$IMAGE"

echo "==> Recreating container '$NAME'  (data persists in: $DATA)"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --restart unless-stopped \
  -p "${PORT}:5050" \
  ${ENVFILE:+--env-file "$ENVFILE"} \
  -v "$DATA:/app/data" \
  "$IMAGE"

echo "==> Done. Open http://localhost:${PORT}/  — settings are stored in $DATA"
