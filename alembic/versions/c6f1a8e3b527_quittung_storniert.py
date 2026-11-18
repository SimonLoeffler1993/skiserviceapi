"""quittung storniert

Revision ID: c6f1a8e3b527
Revises: b8d2f4a6c013
Create Date: 2026-11-18 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6f1a8e3b527'
down_revision: Union[str, Sequence[str], None] = 'b8d2f4a6c013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Bestehende Quittungen gelten als nicht storniert
    op.add_column('quittungen', sa.Column('Storniert', sa.Boolean(), server_default='0', nullable=False))
    op.add_column('quittungen', sa.Column('Storniert_Am', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('quittungen', 'Storniert_Am')
    op.drop_column('quittungen', 'Storniert')
