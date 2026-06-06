# GitHub Actions Deploy

Hamravesh/Darkube is configured to build the app image using GitHub Actions.
Deployment is done manually in the Hamravesh panel by changing the image tag.

## What Changed

The app must not use `nginx` as the image name. The workflow in:

```text
.github/workflows/main.yml
```

builds this repository's `Dockerfile` with:

```text
IMAGE_NAME=registry.hamdocker.ir/erfanclash20178-calm-moon/torobjan
```

## GitHub Secrets

In the GitHub repository, go to:

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

Add these three secrets exactly as Hamravesh shows them:

```text
APP_ID_TOROBJAN_ERFANCLASH20178_CALM_MOON_HAMRAVESH_C11
DEPLOY_TOKEN_TOROBJAN_ERFANCLASH20178_CALM_MOON_HAMRAVESH_C11
DOCKER_AUTH_CONFIG
```

Use the copy buttons in Hamravesh for the values.

## Hamravesh App Runtime Env

These are not GitHub secrets. Set them inside the Hamravesh app environment variables page:

```text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://postgres:9lARfg0b8UOVrhhMJCXS@torobjan-proxy.erfanclash20178-calm-moon.svc:5432/postgres
ADMIN_PASSWORD=<choose-a-strong-password>
SESSION_SECRET=Bmhfd4TwncNUzktzegZYYSvwwa7Z-UEBW4WUnT_ieSlMQwEPIHXygsYQU8YY4v73
UPLOAD_DIR=/data/uploads
TOROB_BASE_URL=https://api.torob.com
TOROB_IW1_HEADER=KWLu4Qcd7RRNKuWAymzNGdmLYfa2wBVmd4ZwwHhcdRjyVqD4VuQwzHy6eCF3witN
TOROB_TIMEOUT_SECONDS=30
TOROB_MAX_RETRIES=1
TOROB_RATE_LIMIT_SECONDS=0.10
```

Do not set these unless Torob tells us to:

```text
TOROB_PROXY_TOKEN
TOROB_COOKIE
TOROB_CSRF_TOKEN
```

## Hamravesh App Settings

Set:

```text
Port: 8000
Readiness Probe: /health
Command: empty
Args/Input: empty
```

The app starts from the Dockerfile entrypoint.

## Deploy Flow

1. Commit and push to the `main` branch.
2. GitHub Actions builds the Docker image.
3. In Hamravesh, set the Docker image to:

```text
registry.hamdocker.ir/erfanclash20178-calm-moon/torobjan
```

4. Set the image tag to the short commit SHA shown in GitHub Actions, for example:

```text
5b6cd9d
```

5. Save changes / deploy in Hamravesh.
6. Open `/health`; it should return `ok`.
7. Login to `/admin/login`.
8. Open `/admin/torob-health`.
9. If Torob health fails, send the production egress IP to Torob for allowlisting.
