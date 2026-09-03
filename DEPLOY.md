# Deploying ACMS

ACMS is a single-node Docker Compose stack. It runs on any Linux box with Docker
Engine and Compose v2 — including a free arm64 host. Two shapes are documented:

| | Primary | Fallback |
|---|---|---|
| Host | Any machine you control (≥ 2 vCPU / 4 GB) | OCI Always Free Ampere A1 (4 OCPU / 24 GB, arm64) |
| Public access | Cloudflare Tunnel (`cloudflared`) | Direct, ports 80/443 |
| TLS | Terminated at Cloudflare's edge (`SITE_ADDRESS=http://localhost`) | Caddy automatic HTTPS (`SITE_ADDRESS=acms.example.com`) |
| Inbound ports | **none** | 80, 443 only |
| Database | `postgres:16` container | `postgres:16` container (**not** Oracle Autonomous DB) |

Both use the exact same `docker-compose.yml`. The only difference is `SITE_ADDRESS`
in `.env` and whether `cloudflared` is running.

## Images (all multi-arch — `linux/amd64` + `linux/arm64`)

| Image | Used by | Notes |
|---|---|---|
| `postgres:16` | `postgres` | Official multi-arch. |
| `valkey/valkey:8` | `valkey` | BSD-3; Redis-protocol drop-in. Official multi-arch. |
| `caddy:2` | `proxy` | Official multi-arch. |
| `node:22-alpine` | frontend build + publish stages | Official multi-arch. |
| `python:3.11-slim` | `api`, `worker`, `seed` (backend Dockerfile) | Official multi-arch. |

Nothing needs `platform:` overrides on an Ampere A1.

## Prerequisites

- Docker Engine + Compose v2 (`docker compose version` ≥ 2.x).
- A copy of this repository on the host.
- For the primary shape: a Cloudflare account, a zone (domain) on it, and
  `cloudflared` installed on the host.
- For the fallback shape: a domain whose A/AAAA record points at the instance's
  public IP, and an OCI security list / NSG allowing ingress on TCP 80 and 443.

## First deploy

```bash
git clone <repo> acms && cd acms
cp .env.example .env
```

Edit `.env`:

- `JWT_SECRET` — set to a long random string (`openssl rand -hex 32`).
- `SITE_ADDRESS`:
  - **Primary (Cloudflare Tunnel):** leave as `http://localhost`. The explicit
    `http://` scheme keeps Caddy on plain HTTP :80 with no certificate and no
    HTTPS redirect; Cloudflare terminates TLS at its edge.
  - **Fallback (direct):** set to your bare domain, e.g. `acms.example.com` (no
    scheme). Caddy then turns on automatic HTTPS and obtains/renews a
    certificate.
- Database passwords: `.env` carries `POSTGRES_OWNER_PASSWORD` /
  `POSTGRES_APP_PASSWORD` (`owner_pw` / `app_pw` by default). On first boot
  `docker/postgres/init/01-roles.sh` reads those two variables to create the
  `acms_owner` / `app_user` roles. The same passwords are embedded in
  `DATABASE_URL` / `MIGRATION_DATABASE_URL` — to change them, edit all four
  values together **before the first `up`** (the init script only runs on an
  empty data directory).

Build and start:

```bash
docker compose up --build -d
```

Run migrations and load demo data (the `seed` service does both — it runs
`alembic upgrade head`, truncates, then inserts the three demo logins, an ingest
API key, and ~150 synthetic alert clusters):

```bash
docker compose run --rm seed
```

The seed output prints the raw ingest API key **once** — copy it if you want to
call `/api/v1/alerts` yourself.

### Primary — attach the Cloudflare Tunnel

```bash
cloudflared tunnel login
cloudflared tunnel create acms
cloudflared tunnel route dns acms acms.example.com
```

Point the tunnel's ingress at the proxy container's published port:

```yaml
# ~/.cloudflared/config.yml
tunnel: acms
credentials-file: /root/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: acms.example.com
    service: http://localhost:80
  - service: http_status:404
```

```bash
cloudflared tunnel run acms      # or install as a systemd service
```

No inbound ports are opened on the host — `cloudflared` dials out to Cloudflare.

### Fallback — OCI Ampere A1

Open 80/443 in the instance's security list (and in the OS firewall:
`sudo firewall-cmd --permanent --add-service={http,https} && sudo firewall-cmd --reload`
on Oracle Linux). With `SITE_ADDRESS` set to your bare domain, Caddy provisions
the certificate on first request. Use a self-hosted `postgres:16` container as in the
compose file — Oracle Autonomous DB is **not** a drop-in (different wire driver
and SQL surface; the async `asyncpg` stack and the migrations target stock
PostgreSQL 16).

## How migrations run

There is no auto-migrate on API startup. Schema changes are applied explicitly:

- **First deploy / demo reset:** `docker compose run --rm seed` (runs
  `alembic upgrade head` then reseeds).
- **Upgrades (keep data):** `docker compose run --rm api alembic upgrade head`.

Alembic connects as the `acms_owner` role (`MIGRATION_DATABASE_URL`); the running
app connects as the least-privilege `app_user`.

## Upgrades

```bash
git pull
docker compose pull            # refresh postgres / valkey / caddy
docker compose up --build -d   # rebuild api / worker / frontend
docker compose run --rm api alembic upgrade head
```

The frontend is rebuilt and re-published to the `webroot` volume on every `up`;
`proxy` waits for that one-shot to finish before it starts serving.

## Backups

The **`pgdata` named volume is the only stateful thing in the stack.** Everything
else — `webroot`, `caddy_data`, `caddy_config`, Valkey — is rebuilt or re-derived
on a cold start.

Nightly logical backup with 7-day retention (`crontab -e` for the deploy user):

```cron
15 2 * * * cd $HOME/acms && docker compose exec -T postgres pg_dump -U acms_owner acms | gzip > $HOME/acms-backups/acms-$(date +\%F).sql.gz && find $HOME/acms-backups -name 'acms-*.sql.gz' -mtime +7 -delete
```

Restore (stops the app, drops and recreates the database, replays the dump):

```bash
docker compose stop api worker
docker compose exec -T postgres psql -U acms_owner -d postgres -c 'DROP DATABASE IF EXISTS acms;' -c 'CREATE DATABASE acms OWNER acms_owner;'
gunzip -c ~/acms-backups/acms-2026-09-01.sql.gz | docker compose exec -T postgres psql -U acms_owner -d acms
docker compose start api worker
```

The dump is plain-format, so it must land in an empty database — dropping first
avoids "already exists" errors on every object.

For a bare-metal move, also copy the backup file off-host (e.g. `rclone` to
object storage).

## What's stateful, what isn't

| Volume / service | Stateful? | On loss |
|---|---|---|
| `pgdata` | **Yes** | Restore from `pg_dump`. This is the system of record. |
| Valkey | No | Cache + ARQ queue only. A cold start loses only in-flight grouping jobs — the alerts are already persisted (persist-then-group), so re-ingesting or a manual re-group recovers them. Safe to `docker compose restart valkey` any time. |
| `webroot` | No | Rebuilt by the `frontend` one-shot on the next `up`. |
| `caddy_data` / `caddy_config` | No | ACME certs are re-issued automatically on next request. |
