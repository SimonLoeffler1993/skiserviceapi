from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Schlüssel/Wert Tabelle für die Anwendungseinstellungen.
# Welche Schlüssel es gibt, welcher Typ und ob geheim, steht in app/services/einstellungen.py
class Einstellung(Base):
    __tablename__ = "einstellungen"
    Schluessel: Mapped[str] = mapped_column(String(100), primary_key=True)
    Wert: Mapped[str | None] = mapped_column(Text, nullable=True)
