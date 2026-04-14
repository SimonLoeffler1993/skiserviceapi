from datetime import date

from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Saison(Base):
    __tablename__ = "saisons"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Start: Mapped[date] = mapped_column(Date)
    Ende: Mapped[date] = mapped_column(Date)
    Name: Mapped[str] = mapped_column(String(50))
    Verwendet: Mapped[int] = mapped_column(Integer)
    SaisonVerleihNummer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)