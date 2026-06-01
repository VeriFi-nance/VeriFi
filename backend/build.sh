#!/usr/bin/env bash
set -o errexit
pip install uv
uv sync
uv run python manage.py collectstatic --noinput

# Neon's free tier auto-suspends the database. The first connection during a
# build can time out while the compute cold-starts, so retry migrate with
# backoff instead of failing the whole deploy on a transient connection error.
migrate_with_retry() {
  local attempts=6
  local delay=10
  local i
  for ((i = 1; i <= attempts; i++)); do
    if uv run python manage.py migrate --noinput; then
      return 0
    fi
    if ((i < attempts)); then
      echo "migrate failed (attempt ${i}/${attempts}); retrying in ${delay}s..."
      sleep "${delay}"
    fi
  done
  echo "migrate failed after ${attempts} attempts" >&2
  return 1
}

migrate_with_retry
