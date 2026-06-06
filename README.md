# Torobjan MVP

FastAPI + HTMX MVP for importing offline seller Excel files, matching rows against Torob base products, collecting seller prices, and exporting an admin Excel file.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

Admin panel: `http://127.0.0.1:8000/admin/login`

## Production deployment

The app is container-ready. On a container platform such as Hamravesh/Darkube, deploy the repository with `Dockerfile`.

Required services:

- Web container from this repo.
- Postgres database.
- Persistent volume mounted at `/data/uploads` if you want to keep original uploaded Excel files after restarts.

Required environment variables:

```text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
ADMIN_PASSWORD=<strong admin password>
SESSION_SECRET=<long random secret>
UPLOAD_DIR=/data/uploads

TOROB_BASE_URL=https://api.torob.com
TOROB_PROXY_TOKEN=
TOROB_COOKIE=
TOROB_CSRF_TOKEN=
TOROB_TIMEOUT_SECONDS=30
TOROB_MAX_RETRIES=1
TOROB_RATE_LIMIT_SECONDS=0.10
```

Startup behavior:

- The container runs `alembic upgrade head`.
- Then it starts `uvicorn app.main:app`.
- Public liveness endpoint: `/health`
- Torob readiness check after admin login: `/admin/torob-health`

Local production-like test:

```powershell
docker compose -f docker-compose.prod.example.yml up --build
```

Production release checklist:

1. Create Postgres and copy its connection URL into `DATABASE_URL`.
2. Set `ADMIN_PASSWORD` and `SESSION_SECRET`; never use the example values.
3. Set `TOROB_BASE_URL=https://api.torob.com` after Torob confirms the server IP is allowlisted.
4. Deploy the container.
5. Open `/health`; it should return `ok`.
6. Login to `/admin/login`.
7. Open `/admin/torob-health`; it should return `OK`.
8. Upload a small 5-row Excel file.
9. If that passes, test the 110-row file.

## Torob access check

Before testing a large Excel file, login as admin and open:

```text
http://127.0.0.1:8000/admin/torob-health
```

If it returns `OK`, Torob search is reachable from the current machine/server.

If it returns `torob_timeout`, turn off VPN or fix the server network path and test again.

If it returns `torob_bot_challenge`, the current machine/server IP is probably not allowed by Torob or is being challenged. Confirm the deployed server IP with Torob, then test again.

If Torob temporarily gives you a gateway, set `TOROB_BASE_URL` to that gateway and put its token in `TOROB_PROXY_TOKEN`. Otherwise keep `TOROB_PROXY_TOKEN` empty.

## Notes

- v1 does not add products directly to Torob.
- Torob search credentials are read from `.env`.
- SQLite is used locally. Set `DATABASE_URL` to a Postgres SQLAlchemy URL for production.
