"""bindungsdaten bestaetigt und fahrertyp

Revision ID: c4e81f2a9b70
Revises: 7b2e9c41d5a3
Create Date: 2026-10-28 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e81f2a9b70'
down_revision: Union[str, Sequence[str], None] = '7b2e9c41d5a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bindungsdaten', sa.Column('Bestaetigt_Am', sa.Date(), nullable=True))
    # Fahrertyp mit Zwischenstufen (1- bis 3+): bestehende 1, 2, 3 werden zu "1", "2", "3"
    op.alter_column('bindungsdaten', 'Fahrkoennen', existing_type=sa.Integer(), type_=sa.String(length=2), existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Zwischenstufen gehen verloren: "2+" bzw. "2-" wird wieder 2
    op.execute("UPDATE bindungsdaten SET Fahrkoennen = LEFT(Fahrkoennen, 1) WHERE Fahrkoennen IS NOT NULL")
    op.alter_column('bindungsdaten', 'Fahrkoennen', existing_type=sa.String(length=2), type_=sa.Integer(), existing_nullable=True)
    op.drop_column('bindungsdaten', 'Bestaetigt_Am')
