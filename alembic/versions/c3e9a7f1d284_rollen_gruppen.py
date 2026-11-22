"""rollen gruppen

Revision ID: c3e9a7f1d284
Revises: b6d2e8f4a173
Create Date: 2026-11-21 10:00:00

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3e9a7f1d284"
down_revision: Union[str, Sequence[str], None] = "b6d2e8f4a173"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Stand dieser Migration, bewusst nicht aus app/core/rechte.py importiert
MITARBEITER_RECHTE = ["skiservice.bearbeiten", "verleih.bearbeiten", "kunden.bearbeiten", "material.bearbeiten", "kasse.kassieren"]


def upgrade() -> None:
    # Rechte: Benutzer -> Gruppen -> Rollen -> Rechte. Ersetzt die feste Spalte benutzer.Rolle
    op.create_table(
        "rollen",
        sa.Column("ID", sa.Integer(), primary_key=True),
        sa.Column("Name", sa.String(100), nullable=False),
        sa.Column("Beschreibung", sa.String(255), nullable=True),
        sa.Column("System", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("Angelegt_Am", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("Name", name="uq_rollen_Name"),
    )
    op.create_table(
        "rolle_rechte",
        sa.Column("Rolle_ID", sa.Integer(), primary_key=True),
        sa.Column("Recht", sa.String(50), primary_key=True),
        sa.ForeignKeyConstraint(["Rolle_ID"], ["rollen.ID"], name="fk_rolle_rechte_rolle", ondelete="CASCADE"),
    )
    op.create_table(
        "gruppen",
        sa.Column("ID", sa.Integer(), primary_key=True),
        sa.Column("Name", sa.String(100), nullable=False),
        sa.Column("Beschreibung", sa.String(255), nullable=True),
        sa.Column("Oidc_Gruppe", sa.String(255), nullable=True),
        sa.Column("Angelegt_Am", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("Name", name="uq_gruppen_Name"),
        sa.UniqueConstraint("Oidc_Gruppe", name="uq_gruppen_Oidc_Gruppe"),
    )
    op.create_table(
        "gruppe_rollen",
        sa.Column("Gruppe_ID", sa.Integer(), primary_key=True),
        sa.Column("Rolle_ID", sa.Integer(), primary_key=True),
        sa.ForeignKeyConstraint(["Gruppe_ID"], ["gruppen.ID"], name="fk_gruppe_rollen_gruppe", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["Rolle_ID"], ["rollen.ID"], name="fk_gruppe_rollen_rolle", ondelete="CASCADE"),
    )
    op.create_table(
        "benutzer_gruppen",
        sa.Column("Benutzer_ID", sa.Integer(), primary_key=True),
        sa.Column("Gruppe_ID", sa.Integer(), primary_key=True),
        sa.Column("Quelle", sa.String(10), nullable=False, server_default="manuell"),
        sa.ForeignKeyConstraint(["Benutzer_ID"], ["benutzer.ID"], name="fk_benutzer_gruppen_benutzer", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["Gruppe_ID"], ["gruppen.ID"], name="fk_benutzer_gruppen_gruppe", ondelete="CASCADE"),
    )
    op.create_index("ix_benutzer_gruppen_Gruppe_ID", "benutzer_gruppen", ["Gruppe_ID"])

    # Bisherige Rollen übernehmen: Administrator (alle Rechte) und Mitarbeiter (Tagesgeschäft)
    jetzt = datetime.now()
    verbindung = op.get_bind()
    rollen = sa.table("rollen", sa.column("ID"), sa.column("Name"), sa.column("Beschreibung"),
                      sa.column("System"), sa.column("Angelegt_Am"))
    gruppen = sa.table("gruppen", sa.column("ID"), sa.column("Name"), sa.column("Beschreibung"), sa.column("Angelegt_Am"))
    op.bulk_insert(rollen, [
        {"ID": 1, "Name": "Administrator", "Beschreibung": "Alle Rechte", "System": True, "Angelegt_Am": jetzt},
        {"ID": 2, "Name": "Mitarbeiter", "Beschreibung": "Tagesgeschäft: Skiservice, Verleih, Kunden, Material, Kasse",
         "System": False, "Angelegt_Am": jetzt},
    ])
    op.bulk_insert(sa.table("rolle_rechte", sa.column("Rolle_ID"), sa.column("Recht")),
                   [{"Rolle_ID": 1, "Recht": "*"}] + [{"Rolle_ID": 2, "Recht": r} for r in MITARBEITER_RECHTE])
    op.bulk_insert(gruppen, [
        {"ID": 1, "Name": "Administratoren", "Beschreibung": "Vollzugriff", "Angelegt_Am": jetzt},
        {"ID": 2, "Name": "Mitarbeiter", "Beschreibung": "Tagesgeschäft", "Angelegt_Am": jetzt},
    ])
    op.bulk_insert(sa.table("gruppe_rollen", sa.column("Gruppe_ID"), sa.column("Rolle_ID")),
                   [{"Gruppe_ID": 1, "Rolle_ID": 1}, {"Gruppe_ID": 2, "Rolle_ID": 2}])
    verbindung.execute(sa.text(
        "INSERT INTO benutzer_gruppen (Benutzer_ID, Gruppe_ID, Quelle) "
        "SELECT ID, CASE WHEN Rolle = 'admin' THEN 1 ELSE 2 END, 'manuell' FROM benutzer"))

    op.drop_column("benutzer", "Rolle")


def downgrade() -> None:
    op.add_column("benutzer", sa.Column("Rolle", sa.String(20), nullable=False, server_default="mitarbeiter"))
    # Admin ist, wer in einer Gruppe mit einer Systemrolle ist
    op.get_bind().execute(sa.text(
        "UPDATE benutzer SET Rolle = 'admin' WHERE ID IN ("
        " SELECT bg.Benutzer_ID FROM benutzer_gruppen bg"
        " JOIN gruppe_rollen gr ON gr.Gruppe_ID = bg.Gruppe_ID"
        " JOIN rollen r ON r.ID = gr.Rolle_ID WHERE r.System = 1)"))
    op.drop_table("benutzer_gruppen")
    op.drop_table("gruppe_rollen")
    op.drop_table("gruppen")
    op.drop_table("rolle_rechte")
    op.drop_table("rollen")
