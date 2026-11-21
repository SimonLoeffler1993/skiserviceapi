"""ohne anmeldung

Revision ID: d5b1f8c2e463
Revises: c3e9a7f1d284
Create Date: 2026-11-21 16:00:00

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d5b1f8c2e463"
down_revision: Union[str, Sequence[str], None] = "c3e9a7f1d284"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Systemgruppe "Ohne Anmeldung": Rechte für alle Aufrufe ohne Anmeldung (bei erzwungener Anmeldung)
    op.add_column("gruppen", sa.Column("Gast", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("gruppen", sa.Column("Lesen", sa.Boolean(), nullable=False, server_default="0"))
    # Ohne Rollen und ohne Lesen: bei erzwungener Anmeldung ändert sich nichts
    op.bulk_insert(
        sa.table("gruppen", sa.column("Name"), sa.column("Beschreibung"), sa.column("Angelegt_Am"),
                 sa.column("Gast"), sa.column("Lesen")),
        [{"Name": "Ohne Anmeldung", "Beschreibung": "Rechte für alle, die nicht angemeldet sind",
          "Angelegt_Am": datetime.now(), "Gast": True, "Lesen": False}],
    )


def downgrade() -> None:
    op.execute("DELETE FROM gruppen WHERE Gast = 1")
    op.drop_column("gruppen", "Lesen")
    op.drop_column("gruppen", "Gast")
