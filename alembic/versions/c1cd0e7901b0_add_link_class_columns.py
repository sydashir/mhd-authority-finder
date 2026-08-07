"""add link class columns

Five additive columns for the wider outbound-link classes (ADR-039). All NOT NULL with a ''
server default, so the 2,237 live rows backfill to empty without a rewrite and without a
window where a read sees NULL. Nothing existing is touched — competitor_links keeps meaning
the brief's contractual 16.

Revision ID: c1cd0e7901b0
Revises: c93a5f21e77b
Create Date: 2026-08-07 18:28:43.013043
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1cd0e7901b0"
down_revision: str | Sequence[str] | None = "c93a5f21e77b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "addiction_directories",
    "mental_health_directories",
    "support_groups",
    "support_groups_found_on",
    # Every outbound domain seen, held so a wider seed list can be applied later without
    # re-crawling. Never published to the sheet.
    "outbound_domains",
)


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column(
            "prospects", sa.Column(column, sa.Text(), server_default="", nullable=False)
        )


def downgrade() -> None:
    for column in reversed(_COLUMNS):
        op.drop_column("prospects", column)
