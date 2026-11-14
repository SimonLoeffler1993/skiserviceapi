"""verleihskiservice

Revision ID: a5c9e3b7d124
Revises: d7b3f5a9e412
Create Date: 2026-11-14 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a5c9e3b7d124"
down_revision: Union[str, Sequence[str], None] = "d7b3f5a9e412"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Services an eigenen Leihski. Wird ein Ski gelöscht, verschwinden seine Services mit.
    op.create_table(
        "verleihskiservice",
        sa.Column("ID", sa.Integer(), primary_key=True),
        sa.Column("EigenSki_ID", sa.Integer(), nullable=False),
        sa.Column("Datum", sa.Date(), nullable=False),
        sa.Column("Bezeichnung", sa.String(200), nullable=False),
        sa.Column("Abzug", sa.Double(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["EigenSki_ID"], ["eigenski.ID"], name="fk_verleihskiservice_eigenski", ondelete="CASCADE"),
    )
    op.create_index("ix_verleihskiservice_EigenSki_ID", "verleihskiservice", ["EigenSki_ID"])


def downgrade() -> None:
    op.drop_index("ix_verleihskiservice_EigenSki_ID", table_name="verleihskiservice")
    op.drop_table("verleihskiservice")
