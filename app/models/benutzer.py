from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class Benutzer(Base):
    """
    Ein Mitarbeiter, der sich im Center oder an der Kasse anmeldet.
    Anmeldung mit Benutzername + Passwort, optional über OIDC und (selbst gesetzt) mit PIN.
    """
    __tablename__ = "benutzer"
    __table_args__ = (
        UniqueConstraint("Benutzername", name="uq_benutzer_Benutzername"),
        UniqueConstraint("Oidc_Issuer", "Oidc_Mandant", "Oidc_Kennung", name="uq_benutzer_oidc"),
    )
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Benutzername: Mapped[str] = mapped_column(String(50), nullable=False)
    Anzeigename: Mapped[str] = mapped_column(String(100), nullable=False)
    Email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    Aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Neuer OIDC-Benutzer, den ein Admin erst freigeben muss
    Freigabe_Ausstehend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Leer bei reinen OIDC-Benutzern
    Passwort_Hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Nach dem Anlegen bzw. Zurücksetzen durch einen Admin muss das Passwort geändert werden
    Passwort_Aendern: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Freiwillig, vom Benutzer selbst gesetzt. Ohne PIN keine Schnellwahl-Kachel
    Pin_Hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # OIDC-Verknüpfung: Issuer aus den Einstellungen, bei Microsoft zusätzlich der Mandant (tid),
    # Kennung = sub bzw. oid (Microsoft)
    Oidc_Issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    Oidc_Mandant: Mapped[str | None] = mapped_column(String(64), nullable=True)
    Oidc_Kennung: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Fehlversuche für Passwort und PIN zusammen, danach Sperre bis Gesperrt_Bis
    Fehlversuche: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    Gesperrt_Bis: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    Angelegt_Am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    Letzte_Anmeldung: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Gruppen (app/models/rechte.py): die Rechte ergeben sich aus deren Rollen
    mitgliedschaften: Mapped[list["BenutzerGruppe"]] = relationship(
        "BenutzerGruppe", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")

    @property
    def darf_anmelden(self) -> bool:
        return bool(self.Aktiv) and not self.Freigabe_Ausstehend


class Geraetesitzung(Base):
    """
    Ein Gerät (Center-Tablet, Kasse) mit seiner Anmeldung. Im Token steht nur der Zufallswert, gespeichert wird sein SHA-256.

    Dauerhaft (über "Gerät anmelden", Recht geraete.anmelden): lange gültig, die Bediener wechseln darauf (PIN).
    Persönlich (normale Anmeldung): gehört zu genau einer Bedienersitzung und endet mit ihr.
    """
    __tablename__ = "geraetesitzungen"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Token_Hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    # "center" oder "kasse"
    Art: Mapped[str] = mapped_column(String(20), nullable=False)
    Angemeldet_Von: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("benutzer.ID", ondelete="CASCADE", name="fk_geraetesitzungen_benutzer"), nullable=True, index=True)
    Erstellt_Am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    Zuletzt_Gesehen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    Laeuft_Ab: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Abmeldung des Bedieners nach so vielen Minuten ohne Aktivität. None = Einstellung, 0 = nie
    Bediener_Timeout_Minuten: Mapped[int | None] = mapped_column(Integer, nullable=True)
    Dauerhaft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="1")


class Bedienersitzung(Base):
    """Der aktive Bediener auf einem angemeldeten Gerät."""
    __tablename__ = "bedienersitzungen"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Token_Hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    Geraetesitzung_ID: Mapped[int] = mapped_column(
        Integer, ForeignKey("geraetesitzungen.ID", ondelete="CASCADE", name="fk_bedienersitzungen_geraet"), nullable=False, index=True)
    Benutzer_ID: Mapped[int] = mapped_column(
        Integer, ForeignKey("benutzer.ID", ondelete="CASCADE", name="fk_bedienersitzungen_benutzer"), nullable=False, index=True)
    # "passwort", "pin" oder "oidc"
    Methode: Mapped[str] = mapped_column(String(20), nullable=False)
    Erstellt_Am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Wird höchstens einmal pro Minute geschrieben
    Letzte_Aktivitaet: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Geraeteschluessel(Base):
    """API-Schlüssel für Geräte ohne Benutzer: Hardware-Scanner und Kundenterminal."""
    __tablename__ = "geraeteschluessel"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # "scanner" oder "terminal"
    Bereich: Mapped[str] = mapped_column(String(20), nullable=False)
    Schluessel_Hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Anfang des Schlüssels zum Wiedererkennen, z.B. "gk_3fA9"
    Praefix: Mapped[str] = mapped_column(String(12), nullable=False)
    Aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    Erstellt_Am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    Erstellt_Von: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("benutzer.ID", ondelete="SET NULL", name="fk_geraeteschluessel_benutzer"), nullable=True)
    Zuletzt_Benutzt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
