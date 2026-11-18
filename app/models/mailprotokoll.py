from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MailProtokoll(Base):
    """
    Eine an einen Kunden versendete Mail mit Inhalt und Sendeergebnis.
    Anhänge werden nicht gespeichert: bei der Quittungs-Mail steht nur der Verweis auf die Quittung.
    """
    __tablename__ = "mail_protokoll"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Gesendet_Am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Schlüssel der Mail-Vorlage, z.B. "skiservice_fertig"
    Vorlage: Mapped[str] = mapped_column(String(50), nullable=False)
    Empfaenger: Mapped[str] = mapped_column(String(255), nullable=False)
    Betreff: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Fertiges HTML, so wie es versendet wurde
    Inhalt: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False, default="")
    Erfolgreich: Mapped[bool] = mapped_column(Boolean, nullable=False)
    Fehler: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Mit dem Kunden verschwinden auch seine Mails, ein gelöschter Auftrag oder Verleih lässt sie beim Kunden stehen
    Kunde_ID: Mapped[int | None] = mapped_column(Integer, ForeignKey("adresse.ID", ondelete="CASCADE"), nullable=True, index=True)
    Auftrag_ID: Mapped[int | None] = mapped_column(Integer, ForeignKey("auftraege.id", ondelete="SET NULL"), nullable=True, index=True)
    Verleih_ID: Mapped[int | None] = mapped_column(Integer, ForeignKey("saisonverleih.ID", ondelete="SET NULL"), nullable=True, index=True)
    # Quittungs-Mail: die angehängte Quittung. Sie hat keinen Kunden, zugeordnet wird über Auftrag bzw. Verleih
    Quittung_ID: Mapped[int | None] = mapped_column(Integer, ForeignKey("quittungen.ID", ondelete="SET NULL"), nullable=True, index=True)
