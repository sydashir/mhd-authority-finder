"""add Both to the source_tag enum

A geography published by BOTH directories yields prospects that serve both. The two-value enum
forced those rows to name one site, so filtering the sheet by AH returned 22 of 2,237 rows and
read as "the AH half was never built" (ADR-037).

Revision ID: c93a5f21e77b
Revises: b7e1d4c92f08
Create Date: 2026-08-06
"""

from alembic import op

revision = "c93a5f21e77b"
down_revision = "b7e1d4c92f08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot be used in the same transaction that adds it, so this
    # runs on its own connection. Postgres has no DROP VALUE, hence the one-way downgrade note.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE source_tag ADD VALUE IF NOT EXISTS 'Both'")


def downgrade() -> None:
    """Postgres cannot remove an enum value; rows would have to be re-tagged first."""
