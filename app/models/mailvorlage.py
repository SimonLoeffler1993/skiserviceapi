from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# Aktueller Stand der Mail-Vorlagen, bearbeitet im Center unter Verwalten -> Vorlagen.
# Welche Vorlagen es gibt und ihre Originaltexte stehen in app/services/mailvorlagen.py
# bzw. app/templates/mail_original/, die Originale werden hier nie überschrieben.
class MailVorlage(Base):
    __tablename__ = "mail_vorlagen"
    Schluessel: Mapped[str] = mapped_column(String(50), primary_key=True)
    # Text mit Platzhaltern als {{name}}
    Betreff: Mapped[str] = mapped_column(String(255), nullable=False)
    # Bereinigtes HTML-Fragment, Platzhalter als <span data-platzhalter>, Bausteine als <div data-baustein>
    Inhalt: Mapped[str] = mapped_column(Text, nullable=False)
    Geaendert_Am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
