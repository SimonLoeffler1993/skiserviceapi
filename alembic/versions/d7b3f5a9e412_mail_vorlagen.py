"""mail_vorlagen

Revision ID: d7b3f5a9e412
Revises: c4e8a2f1d306
Create Date: 2026-11-13 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7b3f5a9e412"
down_revision: Union[str, Sequence[str], None] = "c4e8a2f1d306"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Die Zeilen legt die API beim Start an (app/services/mailvorlagen.py: beim_start),
    # dabei werden auch die alten Betreff-Einstellungen übernommen.
    op.create_table(
        "mail_vorlagen",
        sa.Column("Schluessel", sa.String(50), primary_key=True),
        sa.Column("Betreff", sa.String(255), nullable=False),
        sa.Column("Inhalt", sa.Text(), nullable=False),
        sa.Column("Geaendert_Am", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("mail_vorlagen")
