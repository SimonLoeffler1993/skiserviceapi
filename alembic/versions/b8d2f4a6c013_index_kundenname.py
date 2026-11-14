"""index kundenname

Revision ID: b8d2f4a6c013
Revises: a5c9e3b7d124
Create Date: 2026-11-14 10:00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8d2f4a6c013'
down_revision: Union[str, Sequence[str], None] = 'a5c9e3b7d124'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Index für die alphabetisch sortierte Kundenliste."""
    op.create_index('ix_adresse_name', 'adresse', ['Nachname', 'Vorname'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_adresse_name', table_name='adresse')
