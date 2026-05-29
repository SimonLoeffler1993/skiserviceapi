from sqlalchemy import Boolean, Integer, String, Double, Date, TIMESTAMP, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import date, datetime
from typing import Optional

from app.db.base import Base
from app.models.kunde import SkiKunde

class Ski(Base):
    __tablename__ = "ski"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True)
    auftrag_id: Mapped[int] = mapped_column("Auftrag_ID", ForeignKey("auftraege.id"), nullable=False)
    service: Mapped[str] = mapped_column("Service", Text, nullable=False)
    preis: Mapped[str] = mapped_column("Preis", Text, nullable=False)
    status: Mapped[Optional[int]] = mapped_column("Status", Integer)
    komentar: Mapped[str] = mapped_column("komentar", Text, nullable=False)
    dabei: Mapped[Optional[int]] = mapped_column("dabei", Integer)
    fertig_date: Mapped[str] = mapped_column("Fertig_Date", String(10), nullable=False)
    bindung_id: Mapped[int] = mapped_column("BindungID", Integer, default=0)
    bindung_check: Mapped[bool] = mapped_column("BindungCheck", Boolean, default=False)
    bindung_preis: Mapped[int] = mapped_column("BindungPreis", Integer, nullable=False)
    name: Mapped[Optional[str]] = mapped_column("Name", String(15))
    band: Mapped[int] = mapped_column("Band", Integer, default=0)
    sack: Mapped[int] = mapped_column("Sack", Integer, default=0)
    bindung_status: Mapped[bool] = mapped_column("BindungStatus", Boolean, default=False)
    gepueft: Mapped[Optional[date]] = mapped_column("Gepueft", Date)

    # Relation zu Auftrag
    auftrag: Mapped["Auftrag"] = relationship("Auftrag", back_populates="skis")


class Auftrag(Base):
    __tablename__ = "auftraege"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kunden_id: Mapped[int] = mapped_column("Kunden_ID", Integer, ForeignKey("adresse.ID"))
    start_date: Mapped[datetime] = mapped_column("Start_Date", TIMESTAMP, server_default=func.now())
    ende_date: Mapped[Optional[str]] = mapped_column("Ende_Date", String(150))
    wie: Mapped[Optional[str]] = mapped_column("Wie", String(1))
    a_ski: Mapped[Optional[str]] = mapped_column("A_Ski", String(11))
    ettiket: Mapped[Optional[str]] = mapped_column("Ettiket", String(5))
    zu: Mapped[str] = mapped_column("ZU", String(10), nullable=False)
    fertig_date: Mapped[Optional[str]] = mapped_column("Fertig_Date", String(10))
    abhol_date: Mapped[Optional[str]] = mapped_column("Abhol_Date", String(10))
    anzahlung: Mapped[Optional[str]] = mapped_column("Anzahlung", String(11))
    bezahlt: Mapped[str] = mapped_column("Bezahlt", String(11), default="nein")
    bezahlt_am: Mapped[Optional[date]] = mapped_column("Bezahlt_Am", Date)
    benachrichtigt: Mapped[str] = mapped_column("Benachrichtigt", String(10), default="nein")
    abgerechnet: Mapped[Optional[int]] = mapped_column("Abgerechnet", Integer)
    uberweisung: Mapped[Optional[int]] = mapped_column("Uberweisung", Integer)
    name: Mapped[Optional[str]] = mapped_column("Name", String(15))
    anz_leih: Mapped[Optional[int]] = mapped_column("AnzLeih", Integer)
    rabat: Mapped[Optional[float]] = mapped_column("Rabat", Double)
    rabat_name: Mapped[Optional[str]] = mapped_column("RabatName", String(25))
    rabat_waerung: Mapped[Optional[int]] = mapped_column("RabatWaerung", Integer)
    leih_versicherung: Mapped[Optional[int]] = mapped_column("Leih_Versicherung", Integer)
    quittung_id: Mapped[Optional[int]] = mapped_column("QuittungID", Integer)

    # Relation zu Ski
    skis: Mapped[list["Ski"]] = relationship(Ski, back_populates="auftrag")
    kunde: Mapped["SkiKunde"] = relationship("SkiKunde")