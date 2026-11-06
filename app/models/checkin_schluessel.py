from datetime import datetime

from sqlalchemy import CHAR, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# Schlüsselpaare der Check-in-App. Gehört in die Haupt-DB und nie in die Zwischendatenbank,
# die Check-in-App darf den privaten Schlüssel nicht erreichen können.
class CheckinSchluessel(Base):
    __tablename__ = "checkin_schluessel"
    # SHA-256 des Public Keys (DER), hex: steht auch an jedem verschlüsselten Datensatz
    schluessel_id: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    # SPKI in Base64, Wert für CHECKIN_PUBLIC_KEY der Check-in-App
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    # PKCS8 als PEM, verlässt die API über keine Schnittstelle
    private_key: Mapped[str] = mapped_column(Text, nullable=False)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
