"""mail protokoll

Revision ID: d3a7c5e9f241
Revises: c6f1a8e3b527
Create Date: 2026-11-18 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "d3a7c5e9f241"
down_revision: Union[str, Sequence[str], None] = "c6f1a8e3b527"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Versendete Kundenmails. Mit dem Kunden verschwinden seine Mails,
    # ein gelöschter Auftrag, Verleih oder eine gelöschte Quittung lässt sie stehen.
    op.create_table(
        "mail_protokoll",
        sa.Column("ID", sa.Integer(), primary_key=True),
        sa.Column("Gesendet_Am", sa.DateTime(), nullable=False),
        sa.Column("Vorlage", sa.String(50), nullable=False),
        sa.Column("Empfaenger", sa.String(255), nullable=False),
        sa.Column("Betreff", sa.String(255), nullable=False),
        sa.Column("Inhalt", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("Erfolgreich", sa.Boolean(), nullable=False),
        sa.Column("Fehler", sa.String(500), nullable=True),
        sa.Column("Kunde_ID", sa.Integer(), nullable=True),
        sa.Column("Auftrag_ID", sa.Integer(), nullable=True),
        sa.Column("Verleih_ID", sa.Integer(), nullable=True),
        sa.Column("Quittung_ID", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["Kunde_ID"], ["adresse.ID"], name="fk_mail_protokoll_kunde", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["Auftrag_ID"], ["auftraege.id"], name="fk_mail_protokoll_auftrag", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["Verleih_ID"], ["saisonverleih.ID"], name="fk_mail_protokoll_verleih", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["Quittung_ID"], ["quittungen.ID"], name="fk_mail_protokoll_quittung", ondelete="SET NULL"),
    )
    op.create_index("ix_mail_protokoll_Kunde_ID", "mail_protokoll", ["Kunde_ID"])
    op.create_index("ix_mail_protokoll_Auftrag_ID", "mail_protokoll", ["Auftrag_ID"])
    op.create_index("ix_mail_protokoll_Verleih_ID", "mail_protokoll", ["Verleih_ID"])
    op.create_index("ix_mail_protokoll_Quittung_ID", "mail_protokoll", ["Quittung_ID"])


def downgrade() -> None:
    op.drop_table("mail_protokoll")
