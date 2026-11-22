from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Text as TextTyp
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ereignis(Base):
    """
    Wer hat wann was getan: Ski fertig, Bindung geprüft, bezahlt, Storno, Einstellung geändert, Anmeldung …
    Der Name des Benutzers wird kopiert, damit der Verlauf nach dem Löschen des Benutzers lesbar bleibt.
    """
    __tablename__ = "ereignisse"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Zeitpunkt: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    # z.B. "ski_fertig", "quittung_storniert", siehe app/services/ereignisse.py
    Art: Mapped[str] = mapped_column(String(50), nullable=False)
    Benutzer_ID: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("benutzer.ID", ondelete="SET NULL", name="fk_ereignisse_benutzer"), nullable=True, index=True)
    Benutzer_Name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Name der Gerätesitzung bzw. des Geräteschlüssels
    Geraet: Mapped[str | None] = mapped_column(String(100), nullable=True)
    Kunde_ID: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("adresse.ID", ondelete="CASCADE", name="fk_ereignisse_kunde"), nullable=True, index=True)
    Auftrag_ID: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auftraege.id", ondelete="SET NULL", name="fk_ereignisse_auftrag"), nullable=True, index=True)
    Verleih_ID: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("saisonverleih.ID", ondelete="SET NULL", name="fk_ereignisse_verleih"), nullable=True, index=True)
    Quittung_ID: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("quittungen.ID", ondelete="SET NULL", name="fk_ereignisse_quittung"), nullable=True, index=True)
    Text: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Zusätzliche Angaben als JSON
    Daten: Mapped[str | None] = mapped_column(TextTyp, nullable=True)
