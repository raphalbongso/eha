#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

# Clear stale Prometheus multiprocess files from previous runs
if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
    rm -rf "${PROMETHEUS_MULTIPROC_DIR:?}"/*
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
    echo "Cleared Prometheus multiprocess dir: $PROMETHEUS_MULTIPROC_DIR"
fi

echo "Starting uvicorn..."
if [ "${APP_ENV:-development}" = "production" ]; then
    echo "Running in production mode (workers=2)"
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 "$@"
else
    echo "Running in development mode"
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} "$@"
fi
