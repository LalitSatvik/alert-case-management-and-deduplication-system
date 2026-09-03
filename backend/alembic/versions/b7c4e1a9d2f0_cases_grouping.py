"""cases + grouping_decisions + case_alert_links, and the deferred alerts.case_id FK

Revision ID: b7c4e1a9d2f0
Revises: de0fe5693ed3
Create Date: 2026-08-31 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c4e1a9d2f0"
down_revision: str | None = "de0fe5693ed3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Hand-reviewed (autogenerate seed): JSONB (not JSON), tz-aware timestamps, all
# FKs named via the project naming convention, unique on ``cases.human_ref`` and
# ``case_alert_links.alert_id``, the ``case_human_ref_seq`` sequence backing
# ``human_ref``, and the deferred ``alerts.case_id`` -> ``cases.id`` FK that
# ``d467b8de4c83_alerts`` could not create because ``cases`` did not exist yet.
#
# Table order matters for the in-line FKs: ``cases`` before ``grouping_decisions``
# and ``case_alert_links``; ``grouping_decisions`` before ``case_alert_links``.
# ``app_user`` grants come from the grants migration's ALTER DEFAULT PRIVILEGES.


def upgrade() -> None:
    op.execute("CREATE SEQUENCE case_human_ref_seq START WITH 1 INCREMENT BY 1")

    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("human_ref", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'Open'"), nullable=False),
        sa.Column("disposition", sa.String(length=64), nullable=True),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("risk_score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("alert_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canonical_from_case_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cases")),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], name="fk_cases_assignee_id_users"),
        sa.ForeignKeyConstraint(
            ["canonical_from_case_id"],
            ["cases.id"],
            name="fk_cases_canonical_from_case_id_cases",
        ),
        sa.UniqueConstraint("human_ref", name=op.f("uq_cases_human_ref")),
    )
    op.create_index("ix_cases_status", "cases", ["status"], unique=False)
    op.create_index("ix_cases_assignee_id", "cases", ["assignee_id"], unique=False)

    op.create_table(
        "grouping_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("matched_rule_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("feature_contributions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_grouping_decisions")),
        sa.ForeignKeyConstraint(
            ["alert_id"], ["alerts.id"], name="fk_grouping_decisions_alert_id_alerts"
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_grouping_decisions_case_id_cases"
        ),
    )
    op.create_index(
        "ix_grouping_decisions_alert_id", "grouping_decisions", ["alert_id"], unique=False
    )

    op.create_table(
        "case_alert_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("grouping_decision_id", sa.Uuid(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("linked_by", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_alert_links")),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_case_alert_links_case_id_cases"
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"], ["alerts.id"], name="fk_case_alert_links_alert_id_alerts"
        ),
        sa.ForeignKeyConstraint(
            ["grouping_decision_id"],
            ["grouping_decisions.id"],
            name="fk_case_alert_links_grouping_decision_id_grouping_decisions",
        ),
        sa.UniqueConstraint("alert_id", name=op.f("uq_case_alert_links_alert_id")),
    )
    op.create_index("ix_case_alert_links_case_id", "case_alert_links", ["case_id"], unique=False)

    op.create_foreign_key(op.f("fk_alerts_case_id_cases"), "alerts", "cases", ["case_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint(op.f("fk_alerts_case_id_cases"), "alerts", type_="foreignkey")
    op.drop_index("ix_case_alert_links_case_id", table_name="case_alert_links")
    op.drop_table("case_alert_links")
    op.drop_index("ix_grouping_decisions_alert_id", table_name="grouping_decisions")
    op.drop_table("grouping_decisions")
    op.drop_index("ix_cases_assignee_id", table_name="cases")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_table("cases")
    op.execute("DROP SEQUENCE case_human_ref_seq")
