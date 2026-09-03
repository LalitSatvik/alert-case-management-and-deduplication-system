# Backend test suite

## Requirements

The test suite talks to **real local services**, not Docker:

- **PostgreSQL 16** on `localhost:5432`, reachable with **superuser** privileges.
  By default the suite connects as a passwordless local superuser named after the
  current OS user (the Homebrew / stock-install default). Override with
  `TEST_PG_SUPERUSER_URL=postgresql://user:pw@host:5432/postgres` if your setup
  differs.
- **Redis 7** on `localhost:6379` (default database).

Tests that need these services are marked `@pytest.mark.infra`.

## The `test_db` fixture (`conftest.py`)

Session-scoped, **not** autouse. When a test asks for it, it idempotently creates
a throwaway topology on the local PostgreSQL server:

| Object                | Detail                                            |
| --------------------- | ------------------------------------------------- |
| `ROLE acms_owner`     | DDL / migration owner, password `owner_pw`        |
| `ROLE app_user`       | least-privilege runtime role, password `app_pw`   |
| `DATABASE acms_test`  | owned by `acms_owner`                             |
| grants                | `app_user` gets `CONNECT` + `USAGE ON SCHEMA public` |

It yields a `TestDatabase` exposing `migration_url` and `app_url`
(`postgresql+asyncpg://…/acms_test`). Thin fixtures `pg_migration_url` and
`pg_app_url` return those strings. Teardown drops the database and both roles
(best-effort — teardown errors never fail the suite).

DDL that cannot run in a transaction (`CREATE`/`DROP DATABASE`) is executed over a
plain `asyncpg` connection (autocommit), terminating other backends first.

## Running

```bash
cd backend
python -m pytest -q            # full suite
python -m pytest -m infra -v   # only infra-dependent tests
python -m pytest -m "not infra" # skip service-dependent tests
```

## Relationship to `docker-compose.yml`

The repo-root `docker-compose.yml` + `docker/postgres/init/01-roles.sql` are the
**deployment** topology (Postgres roles, Redis, MinIO, api, worker). They are the
source of truth for a real deployment but are **not** used by this test suite in
the repo's current CI — the `test_db` fixture reproduces the equivalent Postgres
roles/database locally instead.
