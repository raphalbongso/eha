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
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
