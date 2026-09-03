"""case_fts_refs -- GIN full-text indexes on alerts.customer_ref / account_ref

FR-SRCH-02: ``GET /cases?q=`` must also match a case by the customer or account
identifier on one of its linked alerts. ``app.cases.search._fts_case_ids`` adds
those two columns to the alert branch of the ``q`` UNION; these indexes back the
new ``to_tsvector('simple', coalesce(<col>, ''))`` expressions verbatim, exactly
like the four in ``e3f1a2b7c8d9_case_fts``.

Both index names end in ``_fts`` so the ``include_object`` guard in
``alembic/env.py`` keeps ``--autogenerate`` from proposing to drop them.

Revision ID: f1a2b3c4d5e6
Revises: e3f1a2b7c8d9
Create Date: 2026-09-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e3f1a2b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_alerts_customer_ref_fts ON alerts "
        "USING gin (to_tsvector('simple', coalesce(customer_ref, '')))"
    )
    op.execute(
        "CREATE INDEX ix_alerts_account_ref_fts ON alerts "
        "USING gin (to_tsvector('simple', coalesce(account_ref, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_alerts_account_ref_fts")
    op.execute("DROP INDEX ix_alerts_customer_ref_fts")
