from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Ort(Base):
    __tablename__ = "postleitzahl"
    Postlz: Mapped[int] = mapped_column(Integer, primary_key=True)
    Ort: Mapped[str | None] = mapped_column(String(30))

    # back_populates von SkiKunde
    adresse: Mapped[list["SkiKunde"]] = relationship(
        "SkiKunde", back_populates="Ort"
    )