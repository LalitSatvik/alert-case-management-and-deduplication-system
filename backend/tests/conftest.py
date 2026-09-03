"""Shared test fixtures for the ACMS backend suite.

The production deployment provisions PostgreSQL roles and the application database
from ``docker/postgres/init/01-roles.sh`` (see ``docker-compose.yml``). The test
suite does **not** use Docker; instead the ``test_db`` fixture bootstraps an
equivalent throwaway topology against a locally running PostgreSQL 16 on
``localhost:5432`` with superuser access.

Topology created (idempotently, dropped first):

* ``ROLE acms_owner``  -- migrations / DDL owner  (password ``owner_pw``)
* ``ROLE app_user``    -- least-privilege runtime role (password ``app_pw``)
* ``DATABASE acms_test`` owned by ``acms_owner``; ``app_user`` gets CONNECT +
  ``USAGE`` on schema ``public``. Table-level grants for ``app_user`` are applied
  by an Alembic migration, exactly as in the deployment.

Role names / passwords / connection URLs all derive from the single set of
constants below so they cannot desync.

Fixture layering:

* ``test_db`` owns the cluster-level objects only (roles + empty database).
* ``migrated_db`` runs ``alembic upgrade head`` against ``migration_url`` on top.
* Per-test ``AsyncSession`` / engine / client fixtures build on ``migrated_db``
  with savepoint-per-test isolation (see that section lower down, and the note on
  why they connect as ``acms_owner``).

Process-wide default env vars (below) let ``app.config.Settings`` be constructed
at import time by modules like ``app.db`` even without a ``backend/.env``;
``setdefault`` means a real environment still wins. ``pg_url`` / ``redis_url``
are shared connection-string fixtures for the integration tests -- ``pg_url``
reuses the ``test_db`` database and ``redis_url`` points at a throwaway local
Redis DB index that is flushed on teardown.
"""

from __future__ import annotations

import asyncio
import contextlib
import getpass
import os
import pathlib
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

import asyncpg
import pytest
import redis.asyncio as redis_asyncio

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

# --- topology constants (single source of truth) ---------------------------

_PG_HOST = "localhost"
_PG_PORT = 5432
_TEST_DB_NAME = "acms_test"

_OWNER_ROLE = "acms_owner"
_APP_ROLE = "app_user"
# Throwaway credentials for a local test cluster only; they mirror
# ``docker/postgres/init/01-roles.sh`` / ``.env.example``.
_OWNER_PASSWORD = "owner_pw"
_APP_PASSWORD = "app_pw"


def _sqlalchemy_url(role: str, password: str, dbname: str) -> str:
    """Build a ``postgresql+asyncpg://`` SQLAlchemy URL from parts."""
    return f"postgresql+asyncpg://{role}:{password}@{_PG_HOST}:{_PG_PORT}/{dbname}"


MIGRATION_URL = _sqlalchemy_url(_OWNER_ROLE, _OWNER_PASSWORD, _TEST_DB_NAME)
APP_URL = _sqlalchemy_url(_APP_ROLE, _APP_PASSWORD, _TEST_DB_NAME)

# Redis logical DB index 15 is reserved for tests and flushed on teardown.
REDIS_TEST_URL = "redis://localhost:6379/15"


# --- process-wide test defaults -----------------------------------------------
# ``app.config.Settings`` has several required fields and is instantiated at
# import time by modules such as ``app.db``. Provide defaults here (before any
# test module imports ``app.*``) so the suite runs without a ``backend/.env``.
# ``setdefault`` means a real environment variable always wins.
_ENV_DEFAULTS = {
    "DATABASE_URL": APP_URL,
    "MIGRATION_DATABASE_URL": MIGRATION_URL,
    "REDIS_URL": REDIS_TEST_URL,
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "minioadmin",
    "MINIO_SECRET_KEY": "minioadmin",
    # >= 32 bytes so PyJWT does not emit InsecureKeyLengthWarning for HS256.
    "JWT_SECRET": "test-secret-that-is-at-least-32-bytes-long",
}
for _key, _value in _ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)


# --- URL helpers ----------------------------------------------------------


def _asyncpg_dsn(sqlalchemy_url: str) -> str:
    """Convert a ``postgresql+asyncpg://`` SQLAlchemy URL to a plain libpq DSN."""
    return sqlalchemy_url.replace("+asyncpg", "", 1)


def _superuser_dsn() -> str:
    """libpq DSN for a local superuser connection to the ``postgres`` database.

    Honours ``TEST_PG_SUPERUSER_URL`` (either ``postgresql://`` or
    ``postgresql+asyncpg://`` form); otherwise assumes a passwordless local
    superuser named after the current OS user (Homebrew / stock Postgres default).
    """
    override = os.environ.get("TEST_PG_SUPERUSER_URL")
    if override:
        return _asyncpg_dsn(override)
    user = getpass.getuser()
    return f"postgresql://{user}@{_PG_HOST}:{_PG_PORT}/postgres"


def _dsn_on_db(dsn: str, dbname: str) -> str:
    """Return ``dsn`` with its database (final path segment) replaced by ``dbname``."""
    base, _, _tail = dsn.rpartition("/")
    return f"{base}/{dbname}"


@dataclass(frozen=True)
class BootstrappedDb:
    """Connection URLs for the bootstrapped throwaway test database.

    Attributes:
        migration_url: ``acms_owner`` (DDL owner) SQLAlchemy URL for ``acms_test``.
        app_url: ``app_user`` (least-privilege) SQLAlchemy URL for ``acms_test``.
    """

    migration_url: str = MIGRATION_URL
    app_url: str = APP_URL

    @property
    def migration_url_asyncpg(self) -> str:
        """``migration_url`` as a plain libpq DSN (no ``+asyncpg``)."""
        return _asyncpg_dsn(self.migration_url)

    @property
    def app_url_asyncpg(self) -> str:
        """``app_url`` as a plain libpq DSN (no ``+asyncpg``)."""
        return _asyncpg_dsn(self.app_url)


# --- bootstrap / teardown --------------------------------------------------


async def _terminate_backends(conn: asyncpg.Connection, dbname: str) -> None:
    await conn.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = $1 AND pid <> pg_backend_pid()",
        dbname,
    )


async def _create_roles_and_db() -> None:
    """Drop-then-create the two roles and the owned database (autocommit DDL)."""
    conn = await asyncpg.connect(_superuser_dsn())
    try:
        await _terminate_backends(conn, _TEST_DB_NAME)
        await conn.execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}"')
        await conn.execute(f'DROP ROLE IF EXISTS "{_APP_ROLE}"')
        await conn.execute(f'DROP ROLE IF EXISTS "{_OWNER_ROLE}"')
        await conn.execute(f"CREATE ROLE \"{_OWNER_ROLE}\" LOGIN PASSWORD '{_OWNER_PASSWORD}'")
        await conn.execute(f"CREATE ROLE \"{_APP_ROLE}\" LOGIN PASSWORD '{_APP_PASSWORD}'")
        await conn.execute(f'CREATE DATABASE "{_TEST_DB_NAME}" OWNER "{_OWNER_ROLE}"')
    finally:
        await conn.close()


async def _grant_app_privileges() -> None:
    """Grant CONNECT + schema USAGE to ``app_user`` (must run inside the new DB)."""
    db_conn = await asyncpg.connect(_dsn_on_db(_superuser_dsn(), _TEST_DB_NAME))
    try:
        await db_conn.execute(f'GRANT CONNECT ON DATABASE "{_TEST_DB_NAME}" TO "{_APP_ROLE}"')
        await db_conn.execute(f'GRANT USAGE ON SCHEMA public TO "{_APP_ROLE}"')
    finally:
        await db_conn.close()


async def _bootstrap() -> None:
    """(Re)create roles + database.

    Safe to run repeatedly (drops first). If a step fails *after* creating some
    objects, run a best-effort ``_teardown()`` so nothing leaks, then re-raise.
    """
    try:
        await _create_roles_and_db()
        await _grant_app_privileges()
    except (asyncpg.PostgresError, OSError):
        await _teardown()
        raise


async def _teardown() -> None:
    """Best-effort drop of the database + roles. Never fails the suite."""
    with contextlib.suppress(asyncpg.PostgresError, OSError):
        conn = await asyncpg.connect(_superuser_dsn())
        try:
            await _terminate_backends(conn, _TEST_DB_NAME)
            await conn.execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}"')
            await conn.execute(f'DROP ROLE IF EXISTS "{_APP_ROLE}"')
            await conn.execute(f'DROP ROLE IF EXISTS "{_OWNER_ROLE}"')
        finally:
            await conn.close()


# --- fixtures --------------------------------------------------------------


@pytest.fixture(scope="session")
def test_db() -> Iterator[BootstrappedDb]:
    """Session-scoped throwaway PostgreSQL topology for the test suite.

    Creates ``acms_owner`` / ``app_user`` roles and an ``acms_test`` database
    owned by ``acms_owner`` on the local PostgreSQL server, yields a
    :class:`BootstrappedDb` with the two connection URLs, then drops everything.

    Not autouse: only tests (or fixtures) that ask for ``test_db`` pay the cost.
    Requires a local PostgreSQL 16 with passwordless superuser access (or
    ``TEST_PG_SUPERUSER_URL`` pointing at one).
    """
    asyncio.run(_bootstrap())
    try:
        yield BootstrappedDb()
    finally:
        asyncio.run(_teardown())


_BACKEND_ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture(scope="session")
def migrated_db(test_db: BootstrappedDb) -> Iterator[BootstrappedDb]:
    """``test_db`` with the full Alembic migration chain applied (``upgrade head``).

    Runs ``alembic upgrade head`` exactly once per session as a subprocess -- the
    shared-venv interpreter (``sys.executable -m alembic``) invoked from
    ``backend/`` so ``alembic.ini`` and ``backend/`` on ``sys.path`` both resolve --
    with ``MIGRATION_DATABASE_URL`` pointed at ``test_db.migration_url`` (the
    ``acms_owner`` DDL role), mirroring how migrations run in the deployment.

    Yields the same :class:`BootstrappedDb` as ``test_db`` (same URLs). The per-test fixtures
    the per-test AsyncSession / engine fixtures build on this so their tests
    see a fully migrated schema. ``test_db`` itself stays migration-free per its
    docstring contract (cluster objects only).
    """
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_ROOT,
        env={**os.environ, "MIGRATION_DATABASE_URL": test_db.migration_url},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "alembic upgrade head failed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    yield test_db


@pytest.fixture(scope="session")
def pg_migration_url(test_db: BootstrappedDb) -> str:
    """SQLAlchemy URL for the ``acms_owner`` (migration/DDL) role on ``acms_test``."""
    return test_db.migration_url


@pytest.fixture(scope="session")
def pg_app_url(test_db: BootstrappedDb) -> str:
    """SQLAlchemy URL for the least-privilege ``app_user`` role on ``acms_test``."""
    return test_db.app_url


@pytest.fixture(scope="session")
def pg_url(test_db: BootstrappedDb) -> str:
    """Shared Postgres URL for integration tests.

    This suite does not use Docker, so it reuses the ``test_db`` database via
    the least-privilege ``app_user`` role rather than spinning up a container.
    """
    return test_db.app_url


@pytest.fixture
async def redis_url() -> AsyncIterator[str]:
    """Shared Redis URL for integration tests (logical DB 15, flushed on teardown)."""
    yield REDIS_TEST_URL
    client = redis_asyncio.from_url(REDIS_TEST_URL)
    try:
        await client.flushdb()
    finally:
        await client.aclose()


# --- per-test async engine / session / client -------------------------
#
# Isolation mechanism: **transaction rollback**. ``db_session`` opens one
# connection, begins an outer transaction, and hands the test an ``AsyncSession``
# bound to that connection with ``join_transaction_mode="create_savepoint"`` --
# so any ``commit()`` inside a request handler only releases a SAVEPOINT, never
# the outer transaction. Teardown rolls the outer transaction back, so every test
# starts from the migrated-but-empty schema. No ``TRUNCATE`` is used (the
# ``app_user`` role has no table privileges until the grants migration; see below).
#
# Role: ``db_engine`` connects as the least-privilege ``app_user``
# (``migrated_db.app_url``) -- the same role the app connects as in production.
# The ``de0fe5693ed3_audit_grants`` migration gave ``app_user`` full CRUD
# on non-audit tables plus INSERT (but not UPDATE/DELETE) on ``audit_events`` and
# UPDATE (but not DELETE) on ``audit_streams``. ``db_session``'s savepoint
# rollback needs no DELETE privilege, so isolation is unaffected.
# ``db_session_factory`` stays on ``acms_owner`` -- see its docstring.
#
# All four fixtures are function-scoped; combined with
# ``asyncio_default_fixture_loop_scope = "function"`` they share one event loop
# per test. Integration tests build on ``db_session`` + ``app_client``.


@pytest.fixture
async def db_engine(migrated_db: BootstrappedDb) -> AsyncIterator[AsyncEngine]:
    """Function-scoped async engine against the migrated ``acms_test`` DB.

    Uses ``NullPool`` so no connection outlives the test, and disposes the engine
    on teardown. Connects as the least-privilege ``app_user`` (see module note on
    role choice).
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(migrated_db.app_url, poolclass=NullPool, future=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Function-scoped ``AsyncSession`` with transaction-rollback isolation.

    Opens a connection, begins an outer transaction, and yields a session bound
    to it with ``join_transaction_mode="create_savepoint"``. Whatever the test
    (or the app code it drives) commits is contained in SAVEPOINTs; the outer
    transaction is rolled back at teardown, giving the next test a clean slate.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    async with db_engine.connect() as conn:
        outer = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()


@pytest.fixture
async def db_session_factory(
    migrated_db: BootstrappedDb,
) -> AsyncIterator[Callable[[], AbstractAsyncContextManager[AsyncSession]]]:
    """Factory of *independent, really-committing* ``AsyncSession``s.

    ``db_session`` gives every test ONE connection wrapped in an outer
    transaction that is rolled back on teardown -- so a ``commit()`` inside it is
    only a released SAVEPOINT and never truly lands. That is perfect for
    isolation but useless for proving that two *genuinely concurrent* database
    transactions serialise.

    ``db_session_factory`` is the escape hatch. Each ::

        async with db_session_factory() as session:
            ...
            await session.commit()

    opens a FRESH connection from a dedicated ``NullPool`` engine (as
    ``acms_owner``) with its own real transaction; the ``commit()`` actually
    writes. Nothing is rolled back for you -- on teardown the fixture
    ``TRUNCATE``s ``audit_events`` / ``audit_streams`` so the next test starts
    clean.

    Contract for tests using it:

    * mark them ``@pytest.mark.infra`` (they need a real PostgreSQL and they
      commit outside the rollback net);
    * touch ONLY the audit tables (those are the only ones truncated);
    * always use it as ``async with``; ``commit()`` explicitly when you want the
      write to persist.

    ``db_session`` is unchanged -- keep using it for everything else.
    """
    from contextlib import asynccontextmanager

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    # Stays on ``acms_owner`` (not ``app_user`` like ``db_engine``): the teardown
    # ``TRUNCATE audit_events, audit_streams`` needs table ownership, and by
    # design ``app_user`` has neither TRUNCATE nor DELETE on the audit tables.
    engine = create_async_engine(migrated_db.migration_url, poolclass=NullPool, future=True)

    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        session = AsyncSession(bind=engine, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()

    try:
        yield _factory
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE audit_events, audit_streams"))
        await engine.dispose()


@pytest.fixture
async def app_client(db_session: AsyncSession, redis_url: str) -> AsyncIterator[AsyncClient]:
    """``httpx.AsyncClient`` bound to ``create_app()`` with DB + Redis isolation.

    The app's ``get_session`` dependency is overridden to yield the test's
    ``db_session`` (so requests and the test share one transaction), and
    ``get_redis`` is overridden to yield a client on the throwaway test Redis
    (logical DB 15, flushed by the ``redis_url`` fixture on teardown) so ingestion
    idempotency never touches the real db 0. Both overrides are cleared on
    teardown.
    """
    from httpx import ASGITransport, AsyncClient

    from app.db import get_session
    from app.main import create_app
    from app.redis import get_redis

    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def _override_get_redis() -> AsyncIterator[redis_asyncio.Redis]:
        client = redis_asyncio.from_url(redis_url, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_redis] = _override_get_redis
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def valid_alert_payload() -> dict[str, object]:
    """A JSON-ready dict that passes ``AlertIn`` validation.

    ``currency`` is 3 uppercase letters, ``event_time`` is a tz-aware ISO string,
    and ``amount`` has <= 4 decimal places -- the three constraints most easily
    tripped. Reused across the ingestion tests; every field is deterministic so
    two posts collide on ``(source_system, external_alert_id)``.
    """
    return {
        "external_alert_id": "ext-alert-001",
        "source_system": "acme-fraud",
        "event_time": "2026-08-30T12:00:00+00:00",
        "amount": "125.5000",
        "currency": "USD",
        "direction": "outbound",
        "customer_ref": "cust-1",
        "merchant_name": "Quick-Cash,  LLC ",
        "mcc": "6011",
        "risk_score": 55,
        "rule_codes": ["R1", "R2"],
        "typologies": ["structuring"],
    }


@pytest.fixture
async def ingest_client(app_client: AsyncClient, make_api_key: object) -> AsyncClient:
    """``app_client`` plus an active ``scope="ingest"`` API key on ``.api_key``.

    The raw key string is stashed as an attribute so tests can send it as the
    ``X-API-Key`` header without threading a second fixture through every call.
    """
    raw = await make_api_key(scope="ingest", active=True)  # type: ignore[operator]
    app_client.api_key = raw  # type: ignore[attr-defined]
    return app_client


@pytest.fixture
async def seed_user(db_session: AsyncSession) -> object:
    """Insert a User (password ``"pw"``, argon2-hashed) with an ``analyst`` role.

    Returns the persisted ``User`` (``expire_on_commit=False``, so its attributes
    stay loaded). Rolled back with the surrounding ``db_session`` transaction.
    """
    from app.auth.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        email="analyst@example.com",
        display_name="Test Analyst",
        password_hash=hash_password("pw"),
    )
    user.roles.append(UserRole(role="analyst"))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def analyst_token() -> str:
    """A signed access token carrying the ``analyst`` role.

    Token-only helper: ``sub`` is a random UUID with no matching DB row. Fine for
    endpoints that authorize purely off the token's ``roles`` claim; tests that
    tie tokens to persisted users seed a real user instead.
    """
    import uuid

    from app.auth.security import create_access_token

    return create_access_token(sub=str(uuid.uuid4()), roles=["analyst"])


@pytest.fixture
def admin_token() -> str:
    """A signed access token carrying the ``admin`` role. See ``analyst_token``."""
    import uuid

    from app.auth.security import create_access_token

    return create_access_token(sub=str(uuid.uuid4()), roles=["admin"])


@pytest.fixture
def readonly_token() -> str:
    """A signed access token carrying the ``readonly`` role. See ``analyst_token``."""
    import uuid

    from app.auth.security import create_access_token

    return create_access_token(sub=str(uuid.uuid4()), roles=["readonly"])


# --- principal-backed tokens + ingest API keys ------------------------
#
# ``analyst_token`` / ``admin_token`` / ``readonly_token`` above mint a JWT with a
# RANDOM ``sub`` and no DB row -- fine for guards that read only the token, but
# ``get_current_principal`` loads the ``User`` by ``sub`` and 401s on an
# unknown one. The fixtures below give tests a *real* authenticated principal.


@pytest.fixture
def seed_principal(db_session: AsyncSession):
    """Return an async factory that inserts a ``User`` + role grants and returns it.

    ``roles=("analyst",)`` by default; pass ``is_active=False`` to test the 403
    path. Password is ``"pw"`` (argon2-hashed). The ``roles`` relationship is
    eagerly refreshed so ``token_for`` can read it without lazy async IO. Rolled
    back with the surrounding ``db_session`` transaction.
    """
    from collections.abc import Sequence

    from app.auth.security import hash_password
    from app.models.user import User, UserRole

    _counter = 0

    async def _make(
        *,
        roles: Sequence[str] = ("analyst",),
        email: str | None = None,
        is_active: bool = True,
    ) -> User:
        nonlocal _counter
        _counter += 1
        user = User(
            email=email or f"principal{_counter}@example.com",
            display_name="Seeded Principal",
            password_hash=hash_password("pw"),
            is_active=is_active,
        )
        for role in roles:
            user.roles.append(UserRole(role=role))
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user, ["roles"])
        return user

    return _make


@pytest.fixture
def token_for():
    """Return ``token_for(user)`` -> a signed *access* token for that user.

    ``user.roles`` must already be loaded (``seed_principal`` refreshes it).
    """
    from app.auth.security import create_access_token

    def _token(user: object) -> str:
        roles = [r.role for r in user.roles]  # type: ignore[attr-defined]
        return create_access_token(sub=str(user.id), roles=roles)  # type: ignore[attr-defined]

    return _token


@pytest.fixture
def make_api_key(db_session: AsyncSession):
    """Return an async factory that inserts an ``ApiKey`` row and returns its RAW key.

    Only the SHA-256 digest is stored (via ``security.generate_api_key``). Pass
    ``active=False`` / ``scope=...`` to exercise the rejection paths. Rolled back
    with the surrounding ``db_session`` transaction.
    """
    from app.auth.security import generate_api_key
    from app.models.user import ApiKey

    _counter = 0

    async def _make(*, active: bool = True, scope: str = "ingest", label: str | None = None) -> str:
        nonlocal _counter
        _counter += 1
        raw, hashed = generate_api_key()
        db_session.add(
            ApiKey(
                label=label or f"test-key-{_counter}",
                hashed_key=hashed,
                scope=scope,
                is_active=active,
            )
        )
        await db_session.commit()
        return raw

    return _make


# --- bulk ingestion -- real-committing client + ARQ worker drainer ---
#
# ``db_session`` / ``app_client`` isolate via a savepoint that never truly lands,
# so a *second* DB connection (the ARQ worker) cannot see what a request wrote.
# ``test_batch_grouping_runs_via_worker`` needs exactly that cross-connection
# visibility, so it swaps in the fixtures below: real ``commit()``s on
# ``app_url``, cleaned up with a ``TRUNCATE`` (as ``acms_owner``) on teardown.


@pytest.fixture
async def committing_session_factory(
    migrated_db: BootstrappedDb,
) -> AsyncIterator[Callable[[], AbstractAsyncContextManager[AsyncSession]]]:
    """Factory of independent, really-committing ``AsyncSession``s on ``app_url``.

    Like ``db_session_factory`` but (a) connects as the least-privilege
    ``app_user`` (mirrors prod / the ASGI app) and (b) TRUNCATEs the full set of
    tables the bulk path + async grouping touch -- ``case_alert_links``,
    ``grouping_decisions``, ``cases``, ``audit_events``, ``audit_streams``,
    ``alerts`` -- on teardown (as ``acms_owner``, which owns them).
    """
    from contextlib import asynccontextmanager

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(migrated_db.app_url, poolclass=NullPool, future=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    try:
        yield _factory
    finally:
        owner = create_async_engine(migrated_db.migration_url, poolclass=NullPool, future=True)
        async with owner.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE case_alert_links, grouping_decisions, cases, "
                    "audit_events, audit_streams, alerts RESTART IDENTITY CASCADE"
                )
            )
        await owner.dispose()
        await engine.dispose()


@pytest.fixture
async def committing_client(
    committing_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    redis_url: str,
) -> AsyncIterator[AsyncClient]:
    """``httpx`` client on ``create_app()`` whose requests *really commit*.

    ``get_session`` yields from ``committing_session_factory`` and
    ``require_ingest_key`` is stubbed (the real key row would live in a savepoint
    the app's own connection can't see). ``redis_url`` is pulled in so the ARQ
    queue on logical DB 15 is flushed on teardown.
    """
    from httpx import ASGITransport, AsyncClient

    from app.auth.deps import require_ingest_key
    from app.db import get_session
    from app.main import create_app
    from app.models.user import ApiKey

    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with committing_session_factory() as session:
            yield session

    async def _override_require_ingest_key() -> ApiKey:
        import uuid as _uuid

        return ApiKey(
            id=_uuid.uuid4(),
            label="batch-test",
            hashed_key="stub",
            scope="ingest",
            is_active=True,
        )

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_ingest_key] = _override_require_ingest_key
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def run_worker_once(
    migrated_db: BootstrappedDb, redis_url: str
) -> AsyncIterator[Callable[[], object]]:
    """Return an async callable that drains the ARQ queue once, in-process.

    Builds a real ``arq.worker.Worker`` in ``burst`` mode against the test Redis
    (logical DB 15) using the production ``group_alerts_job`` / ``on_startup`` /
    ``on_shutdown``. ``ACMS_WORKER_DATABASE_URL`` points the worker's engine at
    the migrated test DB (``app_url``, mirroring prod) for the duration.
    """
    from arq.connections import RedisSettings
    from arq.worker import Worker

    from app.worker import group_alerts_job, on_shutdown, on_startup

    prev = os.environ.get("ACMS_WORKER_DATABASE_URL")
    os.environ["ACMS_WORKER_DATABASE_URL"] = migrated_db.app_url

    async def _run() -> None:
        worker = Worker(
            functions=[group_alerts_job],
            redis_settings=RedisSettings.from_dsn(redis_url),
            burst=True,
            handle_signals=False,
            keep_result=0,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
        )
        try:
            await worker.async_run()
        finally:
            # Not worker.close(): that path calls the arq-internal deprecated
            # pool.close(). Run our own on_shutdown + aclose the redis pool.
            await on_shutdown(worker.ctx)
            if worker._pool is not None:
                await worker._pool.aclose()

    try:
        yield _run
    finally:
        if prev is None:
            os.environ.pop("ACMS_WORKER_DATABASE_URL", None)
        else:
            os.environ["ACMS_WORKER_DATABASE_URL"] = prev


# --- grouping-engine fixtures ---------------------------------------


@pytest.fixture
def grouping_config() -> object:
    """The parsed ``config/grouping.yaml`` :class:`~app.grouping.GroupingConfig`.

    The suite runs from ``backend/`` so the relative path resolves; kept separate
    from ``app.grouping.config.get_grouping_config`` (which is process-cached and
    settings-driven) so a test can pass an explicit config object.
    """
    from app.grouping.config import load_config

    return load_config("config/grouping.yaml")


@pytest.fixture
def make_alert(db_session: AsyncSession):
    """Async factory that inserts + flushes a minimal :class:`~app.models.alert.Alert`.

    ``minutes`` offsets ``event_time`` from a fixed base instant (so pairs land a
    known distance apart); the ref / id / amount / risk_score / case_id kwargs
    fill only the columns the grouping engine reads. Rolled back with the
    surrounding ``db_session`` transaction.
    """
    import uuid as _uuid
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from app.models.alert import Alert

    base = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    counter = 0

    async def _make(
        *,
        minutes: int = 0,
        account_ref: str | None = None,
        counterparty_ref: str | None = None,
        customer_ref: str | None = None,
        device_id: str | None = None,
        ip_address: str | None = None,
        session_id: str | None = None,
        merchant_name_normalised: str | None = None,
        amount: str | Decimal = "100",
        risk_score: int | None = None,
        case_id: _uuid.UUID | None = None,
        typologies: list[str] | None = None,
    ) -> Alert:
        nonlocal counter
        counter += 1
        alert = Alert(
            external_alert_id=f"grp-ext-{counter}",
            source_system="grouping-test",
            event_time=base + timedelta(minutes=minutes),
            amount=Decimal(str(amount)),
            currency="USD",
            direction="outbound",
            account_ref=account_ref,
            counterparty_ref=counterparty_ref,
            customer_ref=customer_ref,
            device_id=device_id,
            ip_address=ip_address,
            session_id=session_id,
            merchant_name_normalised=merchant_name_normalised,
            risk_score=risk_score,
            case_id=case_id,
            typologies=typologies or [],
        )
        db_session.add(alert)
        await db_session.flush()
        return alert

    return _make


# --- case lifecycle, assignment, notes --------------------------


@pytest.fixture
def make_case(db_session: AsyncSession):
    """Async factory: insert + flush an :class:`~app.models.case.Case`, return it.

    Each call generates a UNIQUE ``human_ref`` (``CASE-<8 hex>``) so tests that
    create several cases never collide on the ``uq_cases_human_ref`` constraint.
    ``status`` defaults to ``"Open"``; any column can be overridden via kwargs.
    ``risk_score`` / ``alert_count`` default to ``0`` (no alerts linked). Flushed
    (so ``id`` / server defaults like ``version`` are populated) but not
    committed; rolled back with the surrounding ``db_session`` transaction.
    """
    import uuid as _uuid

    from app.models.case import Case

    async def _make(status: str = "Open", **overrides: object) -> Case:
        params: dict[str, object] = {
            "human_ref": f"CASE-{_uuid.uuid4().hex[:8]}",
            "status": status,
            "risk_score": 0,
            "alert_count": 0,
        }
        params.update(overrides)
        case = Case(**params)
        db_session.add(case)
        await db_session.flush()
        return case

    return _make


@pytest.fixture
async def seeded_case(make_case: object) -> object:
    """One freshly-``Open`` :class:`~app.models.case.Case` (see ``make_case``)."""
    return await make_case()  # type: ignore[operator]


@pytest.fixture
def make_user(db_session: AsyncSession):
    """Async factory: insert + flush a :class:`~app.models.user.User`, return it.

    ``roles`` is an iterable of role names (empty by default); ``is_active``
    defaults to ``True``. Password is ``"pw"`` (argon2-hashed). The ``roles``
    relationship is refreshed so callers can read it without lazy async IO.
    Flushed but not committed; rolled back with the ``db_session`` transaction.
    """
    from collections.abc import Sequence

    from app.auth.security import hash_password
    from app.models.user import User, UserRole

    _counter = 0

    async def _make(
        *,
        roles: Sequence[str] = (),
        is_active: bool = True,
        email: str | None = None,
    ) -> User:
        nonlocal _counter
        _counter += 1
        user = User(
            email=email or f"notes-user{_counter}@example.com",
            display_name="Notes Test User",
            password_hash=hash_password("pw"),
            is_active=is_active,
        )
        for role in roles:
            user.roles.append(UserRole(role=role))
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user, ["roles"])
        return user

    return _make


@pytest.fixture
async def admin_user(make_user: object) -> object:
    """An active :class:`~app.models.user.User` holding the ``admin`` role."""
    return await make_user(roles=("admin",))  # type: ignore[operator]


@pytest.fixture
async def inactive_user(make_user: object) -> object:
    """A :class:`~app.models.user.User` row with ``is_active=False``."""
    return await make_user(is_active=False)  # type: ignore[operator]


# --- case retrieval (list / search / filter + detail) --------------


async def _link_alert_to_case(
    db_session: AsyncSession,
    case_id: object,
    alert: object,
    *,
    method: str = "deterministic",
) -> None:
    """Insert a ``GroupingDecision`` + ``CaseAlertLink`` joining ``alert`` to a case.

    A lightweight stand-in for a real engine run: enough for the retrieval paths
    (EXISTS-over-alerts filters, the detail view's alert list) without the
    non-determinism of ``apply_grouping_for_alert``.
    """
    from datetime import UTC, datetime

    from app.models.case import CaseAlertLink
    from app.models.grouping import GroupingDecision

    now = datetime.now(UTC)
    decision = GroupingDecision(
        alert_id=alert.id,  # type: ignore[attr-defined]
        case_id=case_id,
        method=method,
        matched_rule_ids=["seed-rule"],
        similarity_score=None,
        feature_contributions={"seed": 1.0},
        engine_version="test",
        config_hash="testhash",
        created_at=now,
    )
    db_session.add(decision)
    await db_session.flush()
    alert.case_id = case_id  # type: ignore[attr-defined]
    db_session.add(
        CaseAlertLink(
            case_id=case_id,
            alert_id=alert.id,  # type: ignore[attr-defined]
            grouping_decision_id=decision.id,
            linked_at=now,
            linked_by="test",
        )
    )
    await db_session.flush()


@pytest.fixture
async def cases_fixture(make_case: object, seed_principal: object) -> dict[str, object]:
    """Two ``Open`` unassigned cases + one ``In Progress`` assigned to an analyst."""
    analyst = await seed_principal(  # type: ignore[operator]
        roles=("analyst",), email="cases-fixture-analyst@example.com"
    )
    open_a = await make_case(status="Open")  # type: ignore[operator]
    open_b = await make_case(status="Open")  # type: ignore[operator]
    in_progress = await make_case(  # type: ignore[operator]
        status="In Progress", assignee_id=analyst.id
    )
    return {
        "analyst": analyst,
        "open": [open_a, open_b],
        "in_progress": in_progress,
    }


@pytest.fixture
async def case_with_merchant(
    make_case: object, make_alert: object, db_session: AsyncSession
) -> object:
    """A case whose one linked alert has ``merchant_name_normalised='quickcash payments'``.

    The alert also carries ``source_system='grouping-test'`` (the ``make_alert``
    default) and ``typologies=['structuring']`` so the source/typology EXISTS
    filters can be exercised against the same fixture.
    """
    case = await make_case(status="Open")  # type: ignore[operator]
    alert = await make_alert(  # type: ignore[operator]
        merchant_name_normalised="quickcash payments",
        typologies=["structuring"],
    )
    await _link_alert_to_case(db_session, case.id, alert)
    return case


@pytest.fixture
async def many_cases(make_case: object) -> list[object]:
    """30 ``Open`` cases (all ``risk_score=0``) for keyset-pagination tests."""
    return [await make_case(status="Open") for _ in range(30)]  # type: ignore[operator]


@pytest.fixture
async def grouped_case(
    db_session: AsyncSession, make_alert: object, grouping_config: object
) -> object:
    """A real canonical case built by ``apply_grouping_for_alert`` over two alerts.

    The two alerts share ``customer_ref`` / ``account_ref`` / ``counterparty_ref``
    / ``amount`` inside every rule window, so the engine deterministically groups
    them into one case with genuine ``GroupingDecision`` rows and a
    ``case.alert_linked`` audit event per alert.
    """
    from app.grouping.persistence import apply_grouping_for_alert

    first = await make_alert(  # type: ignore[operator]
        minutes=0,
        customer_ref="cust-grouped",
        account_ref="acct-grouped",
        counterparty_ref="cp-grouped",
        amount="100",
        risk_score=40,
    )
    case, _ = await apply_grouping_for_alert(db_session, first, grouping_config, "test")
    second = await make_alert(  # type: ignore[operator]
        minutes=30,
        customer_ref="cust-grouped",
        account_ref="acct-grouped",
        counterparty_ref="cp-grouped",
        amount="100",
        risk_score=60,
    )
    await apply_grouping_for_alert(db_session, second, grouping_config, "test")
    await db_session.flush()
    return case


# --- audit-trail export -------------------------------------------


@pytest.fixture
async def worked_case(
    db_session: AsyncSession,
    make_alert: object,
    grouping_config: object,
    seed_principal: object,
) -> object:
    """A real canonical case that has actually been worked.

    Built by ``apply_grouping_for_alert`` over two deterministically-grouped
    alerts (so it has genuine ``GroupingDecision`` rows and a ``case.alert_linked``
    audit event per alert), then moved Open -> In Progress via ``transition_case``
    and given one analyst note via ``add_note``. The ``case:{id}`` stream therefore
    carries ``case.alert_linked``, ``case.transitioned`` and ``case.note_added``
    events, and the change is committed. Returns the :class:`~app.models.case.Case`.
    """
    from app.auth.deps import Principal
    from app.cases.service import add_note, transition_case
    from app.grouping.persistence import apply_grouping_for_alert

    author = await seed_principal(  # type: ignore[operator]
        roles=("analyst",), email="worked-case-analyst@example.com"
    )
    actor = Principal(user_id=str(author.id), email=author.email, roles=["analyst"])

    first = await make_alert(  # type: ignore[operator]
        minutes=0,
        customer_ref="cust-worked",
        account_ref="acct-worked",
        counterparty_ref="cp-worked",
        amount="100",
        risk_score=40,
    )
    case, _ = await apply_grouping_for_alert(db_session, first, grouping_config, "test")
    second = await make_alert(  # type: ignore[operator]
        minutes=30,
        customer_ref="cust-worked",
        account_ref="acct-worked",
        counterparty_ref="cp-worked",
        amount="100",
        risk_score=60,
    )
    await apply_grouping_for_alert(db_session, second, grouping_config, "test")

    await transition_case(db_session, case.id, "In Progress", None, None, actor)
    await add_note(db_session, case.id, "Reviewed both alerts; escalating.", actor)
    await db_session.commit()
    return case
