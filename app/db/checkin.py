"""
Zwischendatenbank der Check-in-App. Eigene Verbindung und eigene Metadaten: Die Tabelle darf nie in die
Migrationen der Haupt-DB geraten, das Schema pflegt alembic_checkin/. Die Check-in-App schreibt per Prisma hinein,
Änderungen müssen dort in prisma/schema.prisma nachgezogen werden.
"""
from datetime import datetime

from sqlalchemy import CHAR, Index, Integer, String, Text, create_engine, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import checkinDbSettings


class CheckinBase(DeclarativeBase):
    pass


class CheckIn(CheckinBase):
    __tablename__ = "checkins"
    __table_args__ = (
        Index("checkins_erstelltAm_idx", "erstelltAm"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    erstelltAm: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schluesselId: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    verschluesselterSchluessel: Mapped[str] = mapped_column(Text, nullable=False)
    iv: Mapped[str] = mapped_column(String(32), nullable=False)
    daten: Mapped[str] = mapped_column(Text, nullable=False)


_session_factory: sessionmaker[Session] | None = None


def eingerichtet() -> bool:
    return bool(checkinDbSettings.host)


def checkin_session() -> Session:
    """Neue Session, die Verbindung wird erst beim ersten Bedarf aufgebaut."""
    global _session_factory
    if _session_factory is None:
        # Kurzer Timeout: eine ausgefallene Zwischendatenbank soll das Center nicht aufhalten
        engine = create_engine(
            checkinDbSettings.url, pool_pre_ping=True, pool_recycle=3600, connect_args={"connect_timeout": 3}
        )
        _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _session_factory()
