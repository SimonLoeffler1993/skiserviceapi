"""auftrag abgeholt am

Revision ID: e4b8d6f0a352
Revises: d3a7c5e9f241
Create Date: 2026-11-18 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b8d6f0a352'
down_revision: Union[str, Sequence[str], None] = 'd3a7c5e9f241'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Tatsächliche Abholung des Auftrags (Wie = "2"), bestehende abgeholte Aufträge bleiben ohne Datum
    op.add_column('auftraege', sa.Column('Abgeholt_Am', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('auftraege', 'Abgeholt_Am')
