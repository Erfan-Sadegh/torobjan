FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    UPLOAD_DIR=/data/uploads

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml alembic.ini README.md ./
COPY app ./app
COPY alembic ./alembic
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /data/uploads

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
