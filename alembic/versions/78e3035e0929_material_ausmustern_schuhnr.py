"""material ausmustern schuhnr

Revision ID: 78e3035e0929
Revises: 8c2a9a2fd9b4
Create Date: 2026-10-21 09:57:36.442280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78e3035e0929'
down_revision: Union[str, Sequence[str], None] = '8c2a9a2fd9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk_skinr_name(bind) -> str | None:
    """Name des Fremdschlüssels saisonverleihmaterial.skinr -> eigenski.SkiNr (war unbenannt)."""
    for fk in sa.inspect(bind).get_foreign_keys("saisonverleihmaterial"):
        if fk["constrained_columns"] == ["skinr"] and fk["referred_table"] == "eigenski":
            return fk["name"]
    return None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # Ausmustern statt löschen, wenn Material schon in einem Verleih steckt
    for tabelle in ("eigenski", "eigenschuh", "verleihstocke"):
        op.add_column(tabelle, sa.Column('Ausgemustert', sa.Boolean(), server_default='0', nullable=False))

    # Eigene Schuh-Nr., bestehende Schuhe behalten ihre ID als Nummer
    op.add_column('eigenschuh', sa.Column('SchuhNr', sa.String(length=50), nullable=True))
    op.execute("UPDATE eigenschuh SET SchuhNr = CAST(ID AS CHAR)")
    op.alter_column('eigenschuh', 'SchuhNr', existing_type=sa.String(length=50), nullable=False)
    op.create_unique_constraint('uq_eigenschuh_SchuhNr', 'eigenschuh', ['SchuhNr'])

    # Ski-Nr. änderbar: Verleihe ziehen über ON UPDATE CASCADE mit
    alter_name = _fk_skinr_name(bind)
    if alter_name:
        op.drop_constraint(alter_name, 'saisonverleihmaterial', type_='foreignkey')
    op.create_foreign_key(
        'fk_saisonverleihmaterial_skinr', 'saisonverleihmaterial', 'eigenski',
        ['skinr'], ['SkiNr'], onupdate='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_saisonverleihmaterial_skinr', 'saisonverleihmaterial', type_='foreignkey')
    op.create_foreign_key(None, 'saisonverleihmaterial', 'eigenski', ['skinr'], ['SkiNr'])

    op.drop_constraint('uq_eigenschuh_SchuhNr', 'eigenschuh', type_='unique')
    op.drop_column('eigenschuh', 'SchuhNr')

    for tabelle in ("eigenski", "eigenschuh", "verleihstocke"):
        op.drop_column(tabelle, 'Ausgemustert')
