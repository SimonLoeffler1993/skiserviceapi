from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Rolle(Base):
    """Bündel von Rechten (app/core/rechte.py). Die Systemrolle hat alle Rechte und ist nicht änderbar."""
    __tablename__ = "rollen"
    __table_args__ = (UniqueConstraint("Name", name="uq_rollen_Name"),)
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    Beschreibung: Mapped[str | None] = mapped_column(String(255), nullable=True)
    System: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    Angelegt_Am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    rechte: Mapped[list["RolleRecht"]] = relationship(
        "RolleRecht", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")


class RolleRecht(Base):
    __tablename__ = "rolle_rechte"
    Rolle_ID: Mapped[int] = mapped_column(
        Integer, ForeignKey("rollen.ID", ondelete="CASCADE", name="fk_rolle_rechte_rolle"), primary_key=True)
    Recht: Mapped[str] = mapped_column(String(50), primary_key=True)


class Gruppe(Base):
    """Benutzer sind Mitglied in Gruppen, Gruppen bekommen Rollen. Optional mit einer Gruppe des OIDC-Anbieters verknüpft."""
    __tablename__ = "gruppen"
    __table_args__ = (
        UniqueConstraint("Name", name="uq_gruppen_Name"),
        UniqueConstraint("Oidc_Gruppe", name="uq_gruppen_Oidc_Gruppe"),
    )
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    Beschreibung: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Name (bzw. bei Microsoft die Object-ID) der Gruppe beim OIDC-Anbieter
    Oidc_Gruppe: Mapped[str | None] = mapped_column(String(255), nullable=True)
    Angelegt_Am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Systemgruppe "Ohne Anmeldung": ihre Rechte gelten für alle Aufrufe ohne Anmeldung (wenn die Anmeldung erzwungen ist)
    Gast: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Nur bei der Gastgruppe: ohne Anmeldung alles ansehen
    Lesen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollen: Mapped[list[Rolle]] = relationship(Rolle, secondary="gruppe_rollen", lazy="selectin")


class GruppeRolle(Base):
    __tablename__ = "gruppe_rollen"
    Gruppe_ID: Mapped[int] = mapped_column(
        Integer, ForeignKey("gruppen.ID", ondelete="CASCADE", name="fk_gruppe_rollen_gruppe"), primary_key=True)
    Rolle_ID: Mapped[int] = mapped_column(
        Integer, ForeignKey("rollen.ID", ondelete="CASCADE", name="fk_gruppe_rollen_rolle"), primary_key=True)


class BenutzerGruppe(Base):
    """Mitgliedschaft. Quelle "oidc" wird bei jeder OIDC-Anmeldung abgeglichen, "manuell" nur im Center."""
    __tablename__ = "benutzer_gruppen"
    Benutzer_ID: Mapped[int] = mapped_column(
        Integer, ForeignKey("benutzer.ID", ondelete="CASCADE", name="fk_benutzer_gruppen_benutzer"), primary_key=True)
    Gruppe_ID: Mapped[int] = mapped_column(
        Integer, ForeignKey("gruppen.ID", ondelete="CASCADE", name="fk_benutzer_gruppen_gruppe"), primary_key=True, index=True)
    Quelle: Mapped[str] = mapped_column(String(10), nullable=False, default="manuell")
