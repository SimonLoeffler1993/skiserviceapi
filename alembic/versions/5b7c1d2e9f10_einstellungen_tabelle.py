"""einstellungen tabelle

Revision ID: 5b7c1d2e9f10
Revises: 4802cf58687e
Create Date: 2026-10-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5b7c1d2e9f10'
down_revision: Union[str, Sequence[str], None] = '4802cf58687e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'einstellungen',
        sa.Column('Schluessel', sa.String(length=100), nullable=False),
        sa.Column('Wert', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('Schluessel'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('einstellungen')
