from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class SkiServicePreise(Base):
    __tablename__ = "dienstleistung"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    Service: Mapped[str] = mapped_column("Service", String(50), nullable=False)
    Preis: Mapped[str] = mapped_column("Preis", String(50), nullable=False)
    Bindung: Mapped[bool] = mapped_column("Check", Boolean, default=None, nullable=True)