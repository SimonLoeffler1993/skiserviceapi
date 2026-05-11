from sqlalchemy import Column, Integer, Date, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date

from app.db.base import Base

# TODO Lex Sync Datum in DB
# Vorne bei Mapped immer Python typen verwenden, hinten bei mapped_column die SQLAlchemy Spaltentypen
class Quittung(Base):
    __tablename__ = "quittungen"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[str] = mapped_column(String)
    AnzAuftrag: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    AnzVerleih: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    Saison_ID: Mapped[int] = mapped_column(Integer)
    Bezahlt_Am: Mapped[date | None] = mapped_column(Date, nullable=True, default=False)
  
    Erstellt_Am: Mapped[date] = mapped_column(Date)
    Ueberweisung: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    Bezahlt: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    BuchhaltungSync: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    LexID: Mapped[str] = mapped_column(String(150))
    NurExtern: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)