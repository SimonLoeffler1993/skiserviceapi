"""nachvollziehbarkeit

Revision ID: b6d2e8f4a173
Revises: a1f7c3e9b250
Create Date: 2026-11-20 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b6d2e8f4a173"
down_revision: Union[str, Sequence[str], None] = "a1f7c3e9b250"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _benutzer_spalte(tabelle: str, spalte: str, fk_name: str) -> None:
    op.add_column(tabelle, sa.Column(spalte, sa.Integer(), nullable=True))
    op.create_foreign_key(fk_name, tabelle, "benutzer", [spalte], ["ID"], ondelete="SET NULL")


def upgrade() -> None:
    # Wer hat angelegt / zuletzt geändert / kassiert / storniert. Alte Datensätze bleiben leer (unbekannt)
    _benutzer_spalte("auftraege", "Angelegt_Von", "fk_auftraege_angelegt_von")
    _benutzer_spalte("auftraege", "Geaendert_Von", "fk_auftraege_geaendert_von")
    op.add_column("auftraege", sa.Column("Geaendert_Am", sa.DateTime(), nullable=True))

    _benutzer_spalte("saisonverleih", "Angelegt_Von", "fk_saisonverleih_angelegt_von")
    _benutzer_spalte("saisonverleih", "Geaendert_Von", "fk_saisonverleih_geaendert_von")
    op.add_column("saisonverleih", sa.Column("Geaendert_Am", sa.DateTime(), nullable=True))

    _benutzer_spalte("quittungen", "Kassiert_Von", "fk_quittungen_kassiert_von")
    _benutzer_spalte("quittungen", "Storniert_Von", "fk_quittungen_storniert_von")


def downgrade() -> None:
    for tabelle, fk, spalte in [
        ("quittungen", "fk_quittungen_storniert_von", "Storniert_Von"),
        ("quittungen", "fk_quittungen_kassiert_von", "Kassiert_Von"),
        ("saisonverleih", "fk_saisonverleih_geaendert_von", "Geaendert_Von"),
        ("saisonverleih", "fk_saisonverleih_angelegt_von", "Angelegt_Von"),
        ("auftraege", "fk_auftraege_geaendert_von", "Geaendert_Von"),
        ("auftraege", "fk_auftraege_angelegt_von", "Angelegt_Von"),
    ]:
        op.drop_constraint(fk, tabelle, type_="foreignkey")
        op.drop_column(tabelle, spalte)
    op.drop_column("saisonverleih", "Geaendert_Am")
    op.drop_column("auftraege", "Geaendert_Am")
