set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting FastAPI..."

uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /usr/src/fastapi