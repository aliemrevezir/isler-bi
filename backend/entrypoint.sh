#!/usr/bin/env bash
# Tek imaj, çok rol: api | worker | beat. docker-compose `command` ile rol seçer.
set -e

ROLE="${1:-api}"

case "$ROLE" in
  api)
    # İlk açılışta şema + seed (idempotent)
    python -m app.seed
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    exec celery -A app.celery_app.celery worker --loglevel=info --concurrency=2
    ;;
  beat)
    exec celery -A app.celery_app.celery beat --loglevel=info
    ;;
  *)
    echo "Bilinmeyen rol: $ROLE (api|worker|beat)" >&2
    exit 1
    ;;
esac
