"""rechte anlegen status

Revision ID: f4b8d1e6a352
Revises: e2a6c9d4f817
Create Date: 2026-11-22 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f4b8d1e6a352"
down_revision: Union[str, Sequence[str], None] = "e2a6c9d4f817"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Bisheriges Recht -> neue Rechte, die es bisher mit abgedeckt hat
AUFTEILUNG = {
    "skiservice.bearbeiten": ["skiservice.anlegen", "skiservice.status"],
    "verleih.bearbeiten": ["verleih.anlegen", "verleih.status"],
    "kunden.bearbeiten": ["kunden.anlegen"],
}


def upgrade() -> None:
    # Bestehende Rollen behalten alles, was sie bisher durften
    for alt, neue in AUFTEILUNG.items():
        for neu in neue:
            op.execute(sa.text(
                "INSERT INTO rolle_rechte (Rolle_ID, Recht) "
                "SELECT r.Rolle_ID, :neu FROM rolle_rechte r WHERE r.Recht = :alt "
                "AND NOT EXISTS (SELECT 1 FROM rolle_rechte x WHERE x.Rolle_ID = r.Rolle_ID AND x.Recht = :neu)"
            ).bindparams(alt=alt, neu=neu))


def downgrade() -> None:
    for neue in AUFTEILUNG.values():
        for neu in neue:
            op.execute(sa.text("DELETE FROM rolle_rechte WHERE Recht = :neu").bindparams(neu=neu))
