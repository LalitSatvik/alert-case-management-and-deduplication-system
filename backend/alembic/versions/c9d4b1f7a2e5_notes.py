"""notes -- append-only case notes

Revision ID: c9d4b1f7a2e5
Revises: b7c4e1a9d2f0
Create Date: 2026-09-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d4b1f7a2e5"
down_revision: str | None = "b7c4e1a9d2f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Hand-written (no autogenerate DB available): tz-aware ``created_at`` with a
# DB-side ``now()`` default, ``retracted`` defaulting false server-side, FKs to
# ``cases.id`` / ``users.id`` named via the project convention, and the
# ``ix_notes_case_id`` lookup index. ``app_user`` CRUD grants are automatic via
# the ALTER DEFAULT PRIVILEGES in the grants migration. There is deliberately no UPDATE/DELETE
# path in the app: the only mutation is ``retract_note``.


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("retracted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("retraction_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notes")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_notes_case_id_cases"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name="fk_notes_author_id_users"),
    )
    op.create_index("ix_notes_case_id", "notes", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notes_case_id", table_name="notes")
    op.drop_table("notes")
