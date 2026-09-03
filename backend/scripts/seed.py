"""Reset the database to a known, fully-worked demo state.

Idempotent: every run brings the database to the *same* end state regardless of
what was there before.

1. ``alembic upgrade head`` (subprocess) -- creates the schema on a fresh
   database, a no-op on an existing one.
2. ``TRUNCATE`` every application table (as the ``acms_owner`` DDL role) and
   restart ``case_human_ref_seq`` -- the cluster / roles / schema are left alone,
   only the data is wiped.
3. Create three users -- ``admin@acms.example.com`` / ``analyst@acms.example.com`` /
   ``auditor@acms.example.com`` (password ``demo-pw``; roles ``admin`` / ``analyst`` /
   ``readonly``) -- and one active ingest ``ApiKey`` whose RAW value is printed
   once to stdout.
4. ``generate(150, (2, 6), 200, seed=1)`` and ingest every row through
   ``ingest_one`` (persist + synchronous grouping + audit), so the post-state is
   deterministic.
5. Walk 5 of the resulting cases Open -> In Progress and add an analyst note.
6. Print a summary.

Local use (outside the compose stack)::

    cd backend
    DATABASE_URL=postgresql+asyncpg://app_user:app_pw@localhost:5432/acms_test \\
    MIGRATION_DATABASE_URL=postgresql+asyncpg://acms_owner:owner_pw@localhost:5432/acms_test \\
    python scripts/seed.py

The database and its roles must already exist (same prerequisite as migrations).
``make seed`` runs the same script inside the compose stack.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.deps import Principal
from app.auth.security import generate_api_key, hash_password
from app.cases.service import add_note, transition_case
from app.config import get_settings
from app.ingestion.service import ingest_one
from app.models.alert import Alert
from app.models.case import Case
from app.models.user import ApiKey, User, UserRole
from app.schemas.alert import AlertIn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_synthetic import generate

_BACKEND_ROOT = Path(__file__).resolve().parent.parent

_APP_TABLES = (
    "case_alert_links",
    "grouping_decisions",
    "notes",
    "audit_events",
    "audit_streams",
    "alerts",
    "cases",
    "user_roles",
    "api_keys",
    "users",
)

_USERS = (
    ("admin@acms.example.com", "Seed Admin", "admin"),
    ("analyst@acms.example.com", "Seed Analyst", "analyst"),
    ("auditor@acms.example.com", "Seed Auditor", "readonly"),
)


def _run_migrations() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade head failed\n{result.stdout}\n{result.stderr}")


async def _truncate(session: AsyncSession) -> None:
    await session.execute(text(f"TRUNCATE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE"))
    await session.execute(text("ALTER SEQUENCE case_human_ref_seq RESTART"))
    await session.commit()


async def _create_users(session: AsyncSession) -> dict[str, User]:
    created: dict[str, User] = {}
    for email, display_name, role in _USERS:
        user = User(
            email=email,
            display_name=display_name,
            password_hash=hash_password("demo-pw"),
        )
        user.roles.append(UserRole(role=role))
        session.add(user)
        created[role] = user
    await session.commit()
    for user in created.values():
        await session.refresh(user)
    return created


async def _create_api_key(session: AsyncSession) -> str:
    raw, hashed = generate_api_key()
    session.add(ApiKey(label="seed-ingest", hashed_key=hashed, scope="ingest", is_active=True))
    await session.commit()
    return raw


async def _ingest_alerts(session: AsyncSession) -> int:
    rows = generate(150, (2, 6), 200, seed=1)
    for row in rows:
        payload = AlertIn(**row)
        await ingest_one(
            session,
            payload,
            idem_key=f"seed:{row['external_alert_id']}",
            actor_label="seed",
        )
    return len(rows)


async def _work_cases(session: AsyncSession, analyst: User) -> int:
    actor = Principal(user_id=str(analyst.id), email=analyst.email, roles=["analyst"])
    case_ids = list(
        (
            await session.execute(
                select(Case.id)
                .where(Case.status == "Open")
                .order_by(Case.created_at, Case.id)
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    for case_id in case_ids:
        await transition_case(session, case_id, "In Progress", "Picked up during seed", None, actor)
        await add_note(session, case_id, "Seed walkthrough: reviewing linked alerts.", actor)
    await session.commit()
    return len(case_ids)


async def _summary(session: AsyncSession) -> tuple[int, int, int]:
    users = int((await session.execute(select(func.count()).select_from(User))).scalar_one())
    alerts = int((await session.execute(select(func.count()).select_from(Alert))).scalar_one())
    cases = int((await session.execute(select(func.count()).select_from(Case))).scalar_one())
    return users, alerts, cases


async def main() -> None:
    _run_migrations()
    settings = get_settings()
    engine = create_async_engine(settings.migration_database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with session_factory() as session:
            await _truncate(session)
            users = await _create_users(session)
            raw_key = await _create_api_key(session)
            n_alerts = await _ingest_alerts(session)
            n_worked = await _work_cases(session, users["analyst"])
            n_users, total_alerts, total_cases = await _summary(session)
    finally:
        await engine.dispose()

    print("\nseed complete")
    print("=============")
    print(f"users            {n_users}  ({', '.join(e for e, _, _ in _USERS)})  password: demo-pw")
    print(f"ingest api key   {raw_key}")
    print(f"alerts ingested  {n_alerts}  (rows in DB: {total_alerts})")
    print(f"cases            {total_cases}  ({n_worked} walked to In Progress with a note)")


if __name__ == "__main__":
    asyncio.run(main())
