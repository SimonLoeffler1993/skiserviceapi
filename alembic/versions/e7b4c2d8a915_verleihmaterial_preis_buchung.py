"""verleihmaterial preis buchung

Revision ID: e7b4c2d8a915
Revises: d9a3f6b2c1e4
Create Date: 2026-10-28 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b4c2d8a915'
down_revision: Union[str, Sequence[str], None] = 'd9a3f6b2c1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Bestehendes Material bleibt ohne gebuchten Preis (Anzeige wie bisher "Saisonverleih")
    op.add_column('saisonverleihmaterial', sa.Column('Preis_ID', sa.Integer(), nullable=True))
    op.add_column('saisonverleihmaterial', sa.Column('PreisBezeichnung', sa.String(length=50), nullable=True))
    op.create_foreign_key(
        'fk_saisonverleihmaterial_preis', 'saisonverleihmaterial', 'saisonverleihpreise',
        ['Preis_ID'], ['ID'], ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_saisonverleihmaterial_preis', 'saisonverleihmaterial', type_='foreignkey')
    op.drop_column('saisonverleihmaterial', 'PreisBezeichnung')
    op.drop_column('saisonverleihmaterial', 'Preis_ID')
