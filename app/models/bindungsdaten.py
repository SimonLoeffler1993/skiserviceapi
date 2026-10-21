from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.kunde import SkiKunde


# Bindungsdaten eines Fahrers zum Zeitpunkt eines Skiservice oder Verleihs.
# Jeder Service-Ski bzw. jede Verleih-Materialzeile bekommt einen eigenen Datensatz,
# über Kunde_ID lassen sich alle Daten eines Kunden abfragen.
# Wird Ski, Auftrag, Material oder Verleih gelöscht, bleibt der Datensatz beim Kunden erhalten (Verweis wird geleert).
class Bindungsdaten(Base):
    __tablename__ = "bindungsdaten"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Kunde_ID: Mapped[int] = mapped_column(ForeignKey("adresse.ID"), index=True, nullable=False)
    Ski_ID: Mapped[int | None] = mapped_column(ForeignKey("ski.ID", ondelete="SET NULL"), unique=True, nullable=True)
    # Materialzeile eines Saison- oder Tagesverleihs
    Material_ID: Mapped[int | None] = mapped_column(ForeignKey("saisonverleihmaterial.ID", ondelete="SET NULL"), unique=True, nullable=True)
    Fahrer: Mapped[str | None] = mapped_column(String(100))
    # Sohlenlänge in mm
    Sohle: Mapped[int | None] = mapped_column(Integer)
    # Gewicht in kg
    Gewicht: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    # Größe in cm (1,80 m = 180)
    Groesse: Mapped[int | None] = mapped_column(Integer)
    # Fahrkönnen Typ 1 (vorsichtig) bis 3 (sportlich)
    Fahrkoennen: Mapped[int | None] = mapped_column(Integer)
    Alter: Mapped[int | None] = mapped_column(Integer)
    Erfasst_Am: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    # Archivierte Einträge werden bei "Letzte Daten abfragen" ausgeblendet
    Archiviert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    kunde: Mapped[SkiKunde] = relationship(SkiKunde)
    ski: Mapped["Ski | None"] = relationship("Ski", back_populates="bindungsdaten")
    material: Mapped["SaisonVerleihMaterial | None"] = relationship("SaisonVerleihMaterial", back_populates="bindungsdaten")
