"""checkin_schluessel

Revision ID: c4e8a2f1d306
Revises: f3a9d1c6b207
Create Date: 2026-11-04 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4e8a2f1d306"
down_revision: Union[str, Sequence[str], None] = "f3a9d1c6b207"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "checkin_schluessel",
        sa.Column("schluessel_id", sa.CHAR(64), primary_key=True),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("private_key", sa.Text(), nullable=False),
        sa.Column("erstellt_am", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("checkin_schluessel")
