# Production Deployment

## Target

Deploy Torobjan as a Dockerized FastAPI app with Postgres.

## Important Torob Note

The local allowlisted IP does not apply to production. After deploying on Hamravesh/Darkube, Torob requests will come from the production server egress IP. Either:

- Ask Torob to allowlist the Hamravesh/Darkube egress IP.
- Or temporarily use the approved gateway:

```text
TOROB_BASE_URL=https://torob-proxy-gateway.darkube.ir
TOROB_PROXY_TOKEN=<gateway-token>
```

For direct Torob API:

```text
TOROB_BASE_URL=https://api.torob.com
TOROB_PROXY_TOKEN=
```

## Required Environment Variables

```text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
ADMIN_PASSWORD=<strong-password>
SESSION_SECRET=<long-random-secret>
UPLOAD_DIR=/data/uploads

TOROB_BASE_URL=https://api.torob.com
TOROB_PROXY_TOKEN=
TOROB_COOKIE=
TOROB_CSRF_TOKEN=
TOROB_TIMEOUT_SECONDS=30
TOROB_MAX_RETRIES=1
TOROB_RATE_LIMIT_SECONDS=0.10
```

## Hamravesh/Darkube Steps

1. Create a Postgres database.
2. Create a Docker app from this repository.
3. Set the environment variables above.
4. Expose container port `8000`.
5. Add a persistent volume mounted at `/data/uploads` if original uploaded files must survive restarts.
6. Deploy.
7. Check public health: `/health`
8. Login to `/admin/login`.
9. Check Torob readiness: `/admin/torob-health`
10. Test a 5-row Excel file.
11. Test the 110-row Excel file.

## Runtime Behavior

- The container runs `alembic upgrade head` before starting the app.
- The app refuses to start in production if:
  - `ADMIN_PASSWORD` is still the default.
  - `SESSION_SECRET` is still the default.
  - `DATABASE_URL` points to SQLite.

## Rollback

If Torob readiness fails in production:

1. Open `/admin/torob-health`.
2. If the error is `torob_bot_challenge`, ask Torob to allowlist the production egress IP or switch to the gateway.
3. If the error is `torob_gateway_not_found`, check gateway deploy/routing.
4. If the error is `torob_timeout`, check network/VPN/firewall.
