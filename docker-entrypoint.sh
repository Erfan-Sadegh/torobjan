#!/bin/sh
set -eu

mkdir -p "${UPLOAD_DIR:-/data/uploads}"

python -c "from app.settings import settings; settings.validate_for_runtime()"

python -m alembic upgrade head

exec python -m uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --proxy-headers
