#!/bin/sh

# Running Gunicorn with Uvicorn workers
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting FastAPI..."

gunicorn main:app \
    --workers 3 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --log-level info \
    --access-logfile - \
    --error-logfile -