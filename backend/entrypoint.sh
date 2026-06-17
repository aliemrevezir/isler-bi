#!/usr/bin/env bash
# Tek imaj, çok rol: api | worker | beat. docker-compose `command` ile rol seçer.
set -e

ROLE="${1:-api}"

case "$ROLE" in
  api)
    # İlk açılışta şema + seed (idempotent)
    python -m app.seed
    if [ -n "$APP_RELOAD" ]; then
      # Dev: kod değişince uvicorn otomatik restart
      exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
    else
      exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    fi
    ;;
  worker)
    if [ -n "$APP_RELOAD" ]; then
      # Dev: .py değişince worker'ı otomatik yeniden başlat (watchdog gerekir)
      exec watchmedo auto-restart --directory=/app/app --pattern='*.py' --recursive -- \
        celery -A app.celery_app.celery worker --loglevel=info --concurrency=2
    else
      exec celery -A app.celery_app.celery worker --loglevel=info --concurrency=2
    fi
    ;;
  beat)
    exec celery -A app.celery_app.celery beat --loglevel=info
    ;;
  *)
    echo "Bilinmeyen rol: $ROLE (api|worker|beat)" >&2
    exit 1
    ;;
esac
