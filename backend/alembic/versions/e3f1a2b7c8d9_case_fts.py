"""case_fts -- GIN full-text indexes backing GET /cases?q=

Revision ID: e3f1a2b7c8d9
Revises: c9d4b1f7a2e5
Create Date: 2026-09-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3f1a2b7c8d9"
down_revision: str | None = "c9d4b1f7a2e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Hand-written: four GIN expression indexes over ``to_tsvector('simple', ...)``.
# ``app.cases.search`` builds the ``q`` filter as a UNION of case ids whose
# ``human_ref`` / linked alert ``external_alert_id`` / ``merchant_name_normalised``
# / note ``body`` match ``plainto_tsquery('simple', q)`` -- these indexes back
# those exact expressions. The two-argument ``to_tsvector(regconfig, text)`` form
# with a literal config is IMMUTABLE, so it is index-eligible. Static SQL only.


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_alerts_merchant_fts ON alerts "
        "USING gin (to_tsvector('simple', coalesce(merchant_name_normalised, '')))"
    )
    op.execute(
        "CREATE INDEX ix_alerts_external_fts ON alerts "
        "USING gin (to_tsvector('simple', coalesce(external_alert_id, '')))"
    )
    op.execute("CREATE INDEX ix_notes_body_fts ON notes USING gin (to_tsvector('simple', body))")
    op.execute(
        "CREATE INDEX ix_cases_human_ref_fts ON cases "
        "USING gin (to_tsvector('simple', human_ref))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_cases_human_ref_fts")
    op.execute("DROP INDEX ix_notes_body_fts")
    op.execute("DROP INDEX ix_alerts_external_fts")
    op.execute("DROP INDEX ix_alerts_merchant_fts")
