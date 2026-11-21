"""geraet anmelden

Revision ID: e2a6c9d4f817
Revises: d5b1f8c2e463
Create Date: 2026-11-21 23:00:00

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2a6c9d4f817"
down_revision: Union[str, Sequence[str], None] = "d5b1f8c2e463"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLE = "Gerät anmelden"
RECHT = "geraete.anmelden"


def upgrade() -> None:
    # Bisherige Geräte bleiben dauerhaft angemeldet; neue Anmeldungen ohne "Gerät anmelden" sind persönlich
    op.add_column("geraetesitzungen", sa.Column("Dauerhaft", sa.Boolean(), nullable=False, server_default="1"))

    verbindung = op.get_bind()
    if verbindung.execute(sa.text("SELECT COUNT(*) FROM rollen WHERE Name = :n"), {"n": ROLLE}).scalar():
        return
    verbindung.execute(
        sa.text("INSERT INTO rollen (Name, Beschreibung, `System`, Angelegt_Am) VALUES (:n, :b, 0, :a)"),
        {"n": ROLLE, "b": "Darf Geräte dauerhaft anmelden", "a": datetime.now()},
    )
    rolle_id = verbindung.execute(sa.text("SELECT ID FROM rollen WHERE Name = :n"), {"n": ROLLE}).scalar()
    verbindung.execute(sa.text("INSERT INTO rolle_rechte (Rolle_ID, Recht) VALUES (:r, :x)"), {"r": rolle_id, "x": RECHT})


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM rollen WHERE Name = :n AND `System` = 0").bindparams(n=ROLLE))
    op.execute(sa.text("DELETE FROM rolle_rechte WHERE Recht = :x").bindparams(x=RECHT))
    op.drop_column("geraetesitzungen", "Dauerhaft")
