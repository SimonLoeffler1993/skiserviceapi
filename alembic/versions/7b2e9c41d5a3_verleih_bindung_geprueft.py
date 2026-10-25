"""verleih bindung geprueft und startstatus je art

Revision ID: 7b2e9c41d5a3
Revises: 463dece4005e
Create Date: 2026-10-25 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b2e9c41d5a3'
down_revision: Union[str, Sequence[str], None] = '463dece4005e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('saisonverleihmaterial', sa.Column('BindungGeprueft', sa.Boolean(), server_default='0', nullable=False))
    op.add_column('saisonverleihmaterial', sa.Column('BindungGeprueft_Am', sa.Date(), nullable=True))

    # Startstatus getrennt für Saison- und Tagesverleih: bisherigen Wert für beide übernehmen
    op.execute(
        "INSERT INTO einstellungen (Schluessel, Wert) "
        "SELECT 'VERLEIH_STARTSTATUS_SAISON', Wert FROM einstellungen WHERE Schluessel = 'VERLEIH_STARTSTATUS'"
    )
    op.execute(
        "INSERT INTO einstellungen (Schluessel, Wert) "
        "SELECT 'VERLEIH_STARTSTATUS_TAG', Wert FROM einstellungen WHERE Schluessel = 'VERLEIH_STARTSTATUS'"
    )
    op.execute("DELETE FROM einstellungen WHERE Schluessel = 'VERLEIH_STARTSTATUS'")


def downgrade() -> None:
    """Downgrade schema."""
    # "vorbereitet" gab es vorher nicht
    op.execute("UPDATE saisonverleih SET Status = 'vorbereitung' WHERE Status = 'vorbereitet'")
    op.execute(
        "INSERT INTO einstellungen (Schluessel, Wert) "
        "SELECT 'VERLEIH_STARTSTATUS', CASE WHEN Wert = 'vorbereitet' THEN 'vorbereitung' ELSE Wert END "
        "FROM einstellungen WHERE Schluessel = 'VERLEIH_STARTSTATUS_SAISON'"
    )
    op.execute("DELETE FROM einstellungen WHERE Schluessel IN ('VERLEIH_STARTSTATUS_SAISON', 'VERLEIH_STARTSTATUS_TAG')")
    op.drop_column('saisonverleihmaterial', 'BindungGeprueft_Am')
    op.drop_column('saisonverleihmaterial', 'BindungGeprueft')
