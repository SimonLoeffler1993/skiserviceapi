from __future__ import annotations
from sqlalchemy import Integer, String, Double, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import date
from typing import Optional

from app.db.base import Base
from app.models.saison import Saison
from app.models.kunde import SkiKunde
from app.models.materialski import EigenSki
from app.models.materialschuh import EigenSchuh
from app.models.materialstock import Skistock


class SkiSaisonverleihPreise(Base):
    __tablename__ = "saisonverleihpreise"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Bezeichnung: Mapped[str] = mapped_column(String(50))
    Preis: Mapped[float] = mapped_column(Double)
    vonL: Mapped[int | None] = mapped_column(Integer)
    bisL: Mapped[int | None] = mapped_column(Integer)
    SkiArt_ID: Mapped[int | None] = mapped_column(Integer)
    inaktiv: Mapped[int] = mapped_column(Integer, default=0)

class SaisonVerleihMaterial(Base):
    __tablename__ = "saisonverleihmaterial"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)

    SaisonVerlei_ID: Mapped[int | None] = mapped_column(ForeignKey("saisonverleih.ID"))
    saisonverleih: Mapped[Optional[SaisonVerleih]] = relationship(
        "SaisonVerleih", back_populates="Material"
    )

    # ON UPDATE CASCADE: Wird die Ski-Nr. geändert, ziehen die Verleihe automatisch mit
    skinr: Mapped[str | None] = mapped_column(String(50), ForeignKey("eigenski.SkiNr", onupdate="CASCADE"))
    Ski: Mapped[Optional[EigenSki]] = relationship(
        EigenSki,
        primaryjoin="SaisonVerleihMaterial.skinr == EigenSki.SkiNr",
        foreign_keys=[skinr],
    )

    schuhnr: Mapped[int | None] = mapped_column(Integer, ForeignKey("eigenschuh.ID"))
    Schuh: Mapped[Optional[EigenSchuh]] = relationship(EigenSchuh)

    stockbez_ID: Mapped[int | None] = mapped_column(Integer, ForeignKey("verleihstocke.ID"))
    Stock: Mapped[Optional[Skistock]] = relationship(Skistock)

    stocklaenge: Mapped[int | None] = mapped_column(Integer)
    Preis: Mapped[float] = mapped_column(Double)
    SkiFahrerName: Mapped[str | None] = mapped_column(String(150), default=None)


class SaisonVerleih(Base):
    __tablename__ = "saisonverleih"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)

    Kunde_ID: Mapped[int | None] = mapped_column(ForeignKey("adresse.ID"))
    Kunde: Mapped[Optional[SkiKunde]] = relationship(SkiKunde)

    Ueberweisung: Mapped[bool | None] = mapped_column(Boolean)
    Bezahlt: Mapped[bool | None] = mapped_column(Boolean)
    Bezahlt_Am: Mapped[date | None] = mapped_column(Date)
    Zurueck: Mapped[int | None] = mapped_column(Integer)
    Zurueck_Am: Mapped[date | None] = mapped_column(Date)
    Bemerkung: Mapped[str | None] = mapped_column(String(500))

    Saison_ID: Mapped[int | None] = mapped_column(ForeignKey("saisons.ID"))
    Saison: Mapped[Optional[Saison]] = relationship(Saison)

    Abgerechnet: Mapped[int | None] = mapped_column(Integer)
    Name: Mapped[str] = mapped_column(String(100))
    Start_Am: Mapped[date] = mapped_column(Date)
    # Nur beim Tagesverleih: letzter Verleihtag
    Ende_Am: Mapped[date | None] = mapped_column(Date, nullable=True)
    # "saison" = Saisonverleih, "tag" = Tagesverleih
    Art: Mapped[str] = mapped_column(String(10), nullable=False, default="saison", server_default="saison")
    QuittungID: Mapped[int | None] = mapped_column(Integer)

    Material: Mapped[list[SaisonVerleihMaterial]] = relationship(
        SaisonVerleihMaterial, back_populates="saisonverleih", cascade="all, delete-orphan"
    )

    @property
    def Tage(self) -> int | None:
        """Anzahl Verleihtage beim Tagesverleih (Start und Ende zählen mit)."""
        if self.Art != "tag" or self.Start_Am is None or self.Ende_Am is None:
            return None
        return (self.Ende_Am - self.Start_Am).days + 1

    @property
    def Bezeichnung(self) -> str:
        """Bezeichnung für Quittung, Kasse und PDF."""
        if self.Art == "tag" and self.Start_Am and self.Ende_Am:
            tage = self.Tage
            return f"Tagesverleih {self.Start_Am:%d.%m.}–{self.Ende_Am:%d.%m.%Y} ({tage} {'Tag' if tage == 1 else 'Tage'})"
        return "Saisonverleih"