"""checkins

Revision ID: a1c0e5d7b901
Revises:
Create Date: 2026-11-04 12:00:00

Die Tabelle wurde anfangs von Prisma angelegt: Eine bestehende bleibt unverändert, Spalten und Index sind dieselben.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "a1c0e5d7b901"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("checkins"):
        return
    op.create_table(
        "checkins",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("erstelltAm", mysql.DATETIME(fsp=3), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(3)")),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schluesselId", sa.CHAR(64), nullable=False),
        sa.Column("verschluesselterSchluessel", sa.Text(), nullable=False),
        sa.Column("iv", sa.String(32), nullable=False),
        sa.Column("daten", sa.Text(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("checkins_erstelltAm_idx", "checkins", ["erstelltAm"])


def downgrade() -> None:
    op.drop_table("checkins")
