"""handware

Revision ID: f3a9d1c6b207
Revises: e7b4c2d8a915
Create Date: 2026-10-30 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a9d1c6b207'
down_revision: Union[str, Sequence[str], None] = 'e7b4c2d8a915'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('handware',
        sa.Column('ID', sa.Integer(), nullable=False),
        sa.Column('Name', sa.String(length=100), nullable=False),
        sa.Column('Beschreibung', sa.String(length=500), nullable=True),
        sa.Column('Kategorie', sa.String(length=50), nullable=True),
        sa.Column('Anzahl', sa.Integer(), nullable=True),
        sa.Column('Preis', sa.Double(), nullable=False),
        sa.PrimaryKeyConstraint('ID')
    )
    # Kopie von Handware-Artikeln auf der Quittung
    op.add_column('quittung_artikel', sa.Column('Bezeichnung', sa.String(length=100), nullable=True))
    op.add_column('quittung_artikel', sa.Column('Preis', sa.Double(), nullable=True))
    op.add_column('quittung_artikel', sa.Column('Menge', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('quittung_artikel', 'Menge')
    op.drop_column('quittung_artikel', 'Preis')
    op.drop_column('quittung_artikel', 'Bezeichnung')
    op.drop_table('handware')
