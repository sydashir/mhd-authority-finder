"""rename competitor_links_found_on -> contact_found_on

Specific Page must be the page the client OPENS, so it now holds the competitor-links page and
this column holds the contact page instead (ADR-036). The old name would describe the opposite
of what the column contains.

Revision ID: b7e1d4c92f08
Revises: a3f2c9d81b47
Create Date: 2026-08-05
"""

from alembic import op

revision = "b7e1d4c92f08"
down_revision = "a3f2c9d81b47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("prospects", "competitor_links_found_on", new_column_name="contact_found_on")


def downgrade() -> None:
    op.alter_column("prospects", "contact_found_on", new_column_name="competitor_links_found_on")
