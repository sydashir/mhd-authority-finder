"""add competitor_links_found_on

The link check covers the detected page AND one resources hop (ADR-011), so a competitor link
frequently lives on a sub-page. The sheet only ever showed the contact URL, so a client opened
row 1 (counseling.ucr.edu), saw no competitor links, and reported a false positive — the links
were real, on the resources page we never named. This column carries that provenance.

Revision ID: a3f2c9d81b47
Revises: 667d952764fb
Create Date: 2026-08-04
"""

import sqlalchemy as sa
from alembic import op

revision = "a3f2c9d81b47"
down_revision = "667d952764fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default "" so the existing rows are backfilled as "same page as Specific Page",
    # which is what blank means — no NULL-vs-empty ambiguity for the sheet writer.
    op.add_column(
        "prospects",
        sa.Column("competitor_links_found_on", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("prospects", "competitor_links_found_on")
