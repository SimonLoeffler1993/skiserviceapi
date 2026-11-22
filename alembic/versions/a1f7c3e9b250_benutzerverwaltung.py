"""benutzerverwaltung

Revision ID: a1f7c3e9b250
Revises: e4b8d6f0a352
Create Date: 2026-11-20 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1f7c3e9b250"
down_revision: Union[str, Sequence[str], None] = "e4b8d6f0a352"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Benutzer mit Passwort, optionaler PIN und optionaler OIDC-Verknüpfung
    op.create_table(
        "benutzer",
        sa.Column("ID", sa.Integer(), primary_key=True),
        sa.Column("Benutzername", sa.String(50), nullable=False),
        sa.Column("Anzeigename", sa.String(100), nullable=False),
        sa.Column("Email", sa.String(255), nullable=True),
        sa.Column("Rolle", sa.String(20), nullable=False, server_default="mitarbeiter"),
        sa.Column("Aktiv", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("Freigabe_Ausstehend", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("Passwort_Hash", sa.String(255), nullable=True),
        sa.Column("Passwort_Aendern", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("Pin_Hash", sa.String(255), nullable=True),
        sa.Column("Oidc_Issuer", sa.String(255), nullable=True),
        sa.Column("Oidc_Mandant", sa.String(64), nullable=True),
        sa.Column("Oidc_Kennung", sa.String(255), nullable=True),
        sa.Column("Fehlversuche", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("Gesperrt_Bis", sa.DateTime(), nullable=True),
        sa.Column("Angelegt_Am", sa.DateTime(), nullable=False),
        sa.Column("Letzte_Anmeldung", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("Benutzername", name="uq_benutzer_Benutzername"),
        sa.UniqueConstraint("Oidc_Issuer", "Oidc_Mandant", "Oidc_Kennung", name="uq_benutzer_oidc"),
    )

    # Angemeldete Geräte (Center-Tablet, Kasse); mit dem Benutzer, der es angemeldet hat, verschwindet die Sitzung
    op.create_table(
        "geraetesitzungen",
        sa.Column("ID", sa.Integer(), primary_key=True),
        sa.Column("Token_Hash", sa.String(64), nullable=False),
        sa.Column("Name", sa.String(100), nullable=False),
        sa.Column("Art", sa.String(20), nullable=False),
        sa.Column("Angemeldet_Von", sa.Integer(), nullable=True),
        sa.Column("Erstellt_Am", sa.DateTime(), nullable=False),
        sa.Column("Zuletzt_Gesehen", sa.DateTime(), nullable=False),
        sa.Column("Laeuft_Ab", sa.DateTime(), nullable=False),
        sa.Column("Bediener_Timeout_Minuten", sa.Integer(), nullable=True),
        sa.UniqueConstraint("Token_Hash", name="uq_geraetesitzungen_Token_Hash"),
        sa.ForeignKeyConstraint(["Angemeldet_Von"], ["benutzer.ID"], name="fk_geraetesitzungen_benutzer", ondelete="CASCADE"),
    )
    op.create_index("ix_geraetesitzungen_Angemeldet_Von", "geraetesitzungen", ["Angemeldet_Von"])

    # Aktiver Bediener auf einem Gerät
    op.create_table(
        "bedienersitzungen",
        sa.Column("ID", sa.Integer(), primary_key=True),
        sa.Column("Token_Hash", sa.String(64), nullable=False),
        sa.Column("Geraetesitzung_ID", sa.Integer(), nullable=False),
        sa.Column("Benutzer_ID", sa.Integer(), nullable=False),
        sa.Column("Methode", sa.String(20), nullable=False),
        sa.Column("Erstellt_Am", sa.DateTime(), nullable=False),
        sa.Column("Letzte_Aktivitaet", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("Token_Hash", name="uq_bedienersitzungen_Token_Hash"),
        sa.ForeignKeyConstraint(["Geraetesitzung_ID"], ["geraetesitzungen.ID"], name="fk_bedienersitzungen_geraet", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["Benutzer_ID"], ["benutzer.ID"], name="fk_bedienersitzungen_benutzer", ondelete="CASCADE"),
    )
    op.create_index("ix_bedienersitzungen_Geraetesitzung_ID", "bedienersitzungen", ["Geraetesitzung_ID"])
    op.create_index("ix_bedienersitzungen_Benutzer_ID", "bedienersitzungen", ["Benutzer_ID"])

    # API-Schlüssel für Hardware-Scanner und Kundenterminal
    op.create_table(
        "geraeteschluessel",
        sa.Column("ID", sa.Integer(), primary_key=True),
        sa.Column("Name", sa.String(100), nullable=False),
        sa.Column("Bereich", sa.String(20), nullable=False),
        sa.Column("Schluessel_Hash", sa.String(64), nullable=False),
        sa.Column("Praefix", sa.String(12), nullable=False),
        sa.Column("Aktiv", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("Erstellt_Am", sa.DateTime(), nullable=False),
        sa.Column("Erstellt_Von", sa.Integer(), nullable=True),
        sa.Column("Zuletzt_Benutzt", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("Name", name="uq_geraeteschluessel_Name"),
        sa.UniqueConstraint("Schluessel_Hash", name="uq_geraeteschluessel_Schluessel_Hash"),
        sa.ForeignKeyConstraint(["Erstellt_Von"], ["benutzer.ID"], name="fk_geraeteschluessel_benutzer", ondelete="SET NULL"),
    )

    # Ereignisprotokoll: mit dem Kunden verschwinden seine Ereignisse, sonst bleiben sie stehen
    op.create_table(
        "ereignisse",
        sa.Column("ID", sa.Integer(), primary_key=True),
        sa.Column("Zeitpunkt", sa.DateTime(), nullable=False),
        sa.Column("Art", sa.String(50), nullable=False),
        sa.Column("Benutzer_ID", sa.Integer(), nullable=True),
        sa.Column("Benutzer_Name", sa.String(100), nullable=True),
        sa.Column("Geraet", sa.String(100), nullable=True),
        sa.Column("Kunde_ID", sa.Integer(), nullable=True),
        sa.Column("Auftrag_ID", sa.Integer(), nullable=True),
        sa.Column("Verleih_ID", sa.Integer(), nullable=True),
        sa.Column("Quittung_ID", sa.Integer(), nullable=True),
        sa.Column("Text", sa.String(500), nullable=False, server_default=""),
        sa.Column("Daten", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["Benutzer_ID"], ["benutzer.ID"], name="fk_ereignisse_benutzer", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["Kunde_ID"], ["adresse.ID"], name="fk_ereignisse_kunde", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["Auftrag_ID"], ["auftraege.id"], name="fk_ereignisse_auftrag", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["Verleih_ID"], ["saisonverleih.ID"], name="fk_ereignisse_verleih", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["Quittung_ID"], ["quittungen.ID"], name="fk_ereignisse_quittung", ondelete="SET NULL"),
    )
    op.create_index("ix_ereignisse_Zeitpunkt", "ereignisse", ["Zeitpunkt"])
    op.create_index("ix_ereignisse_Benutzer_ID", "ereignisse", ["Benutzer_ID"])
    op.create_index("ix_ereignisse_Kunde_ID", "ereignisse", ["Kunde_ID"])
    op.create_index("ix_ereignisse_Auftrag_ID", "ereignisse", ["Auftrag_ID"])
    op.create_index("ix_ereignisse_Verleih_ID", "ereignisse", ["Verleih_ID"])
    op.create_index("ix_ereignisse_Quittung_ID", "ereignisse", ["Quittung_ID"])


def downgrade() -> None:
    op.drop_table("ereignisse")
    op.drop_table("geraeteschluessel")
    op.drop_table("bedienersitzungen")
    op.drop_table("geraetesitzungen")
    op.drop_table("benutzer")
