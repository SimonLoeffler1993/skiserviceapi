from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Skistock(Base):
    __tablename__ = "verleihstocke"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Bezeichnung: Mapped[str] = mapped_column(String(100), nullable=False)