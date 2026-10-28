"""saisonverleih benachrichtigt

Revision ID: d9a3f6b2c1e4
Revises: c4e81f2a9b70
Create Date: 2026-10-28 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9a3f6b2c1e4'
down_revision: Union[str, Sequence[str], None] = 'c4e81f2a9b70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Bestehende Verleihe gelten als nicht benachrichtigt
    op.add_column('saisonverleih', sa.Column('Benachrichtigt', sa.String(length=10), server_default='nein', nullable=False))
    op.add_column('saisonverleih', sa.Column('Benachrichtigt_Am', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('saisonverleih', 'Benachrichtigt_Am')
    op.drop_column('saisonverleih', 'Benachrichtigt')
