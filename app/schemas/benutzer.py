from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Rolle = Literal["admin", "mitarbeiter"]
GeraetArt = Literal["center", "kasse"]
SchluesselBereich = Literal["scanner", "terminal"]

BENUTZERNAME_MUSTER = r"^[A-Za-z0-9._@-]{2,50}$"


# --- Anmeldung -------------------------------------------------------------

class OidcStatus(BaseModel):
    aktiv: bool
    anbieter: str
    button_text: str


class AuthStatus(BaseModel):
    einrichtung_noetig: bool
    anmeldung_erzwungen: bool
    geraeteschluessel_erzwungen: bool
    pin_erlaubt: bool
    oidc: OidcStatus


class GeraetAngaben(BaseModel):
    # Nur nötig, wenn das Gerät noch nicht angemeldet ist (kein Bearer sg_/sb_)
    geraet_name: Optional[str] = Field(default=None, max_length=100)
    geraet_art: GeraetArt = "center"


class AnmeldenAnfrage(GeraetAngaben):
    benutzername: str = Field(min_length=1, max_length=50)
    passwort: str = Field(min_length=1, max_length=256)


class EinrichtungAnfrage(GeraetAngaben):
    benutzername: str = Field(pattern=BENUTZERNAME_MUSTER)
    anzeigename: str = Field(min_length=1, max_length=100)
    passwort: str = Field(min_length=1, max_length=256)
    email: Optional[str] = Field(default=None, max_length=255)


class PinAnmeldung(BaseModel):
    benutzer_id: int
    pin: str = Field(pattern=r"^\d{4,8}$")


class OidcEinloesen(GeraetAngaben):
    code: str = Field(min_length=10, max_length=200)


class OidcVerknuepfen(BaseModel):
    # Rücksprung nach der Anmeldung beim Anbieter, muss in ERLAUBTE_URSPRUENGE liegen
    ziel: str = Field(max_length=500)


class OidcUrl(BaseModel):
    url: str


class IchBenutzer(BaseModel):
    id: int
    benutzername: str
    anzeigename: str
    email: Optional[str] = None
    rolle: Rolle
    hat_passwort: bool
    hat_pin: bool
    passwort_aendern: bool
    oidc_verknuepft: bool
    oidc_veraltet: bool


class IchGeraet(BaseModel):
    id: int
    name: str
    art: str
    bediener_timeout_minuten: int


class IchAntwort(BaseModel):
    benutzer: Optional[IchBenutzer] = None
    geraet: Optional[IchGeraet] = None
    # Anmeldung mit Bediener-Token über PIN, Passwort oder OIDC
    methode: Optional[str] = None


class AnmeldeAntwort(BaseModel):
    # Nur bei neuer Gerätesitzung, sonst None (das vorhandene Geräte-Token bleibt gültig)
    geraet_token: Optional[str] = None
    bediener_token: str
    benutzer: IchBenutzer
    geraet: IchGeraet


class Kachel(BaseModel):
    id: int
    anzeigename: str


class EigenesPasswort(BaseModel):
    # Leer erlaubt, wenn noch kein Passwort gesetzt ist (reiner OIDC-Benutzer)
    alt: Optional[str] = Field(default=None, max_length=256)
    neu: str = Field(min_length=1, max_length=256)


class EigenePin(BaseModel):
    # Bestätigung mit dem aktuellen Passwort; reine OIDC-Benutzer kurz nach der OIDC-Anmeldung ohne
    passwort: Optional[str] = Field(default=None, max_length=256)
    pin: str = Field(pattern=r"^\d{4,8}$")


class TicketAnfrage(BaseModel):
    pfad: str = Field(max_length=200)


class TicketAntwort(BaseModel):
    ticket: str
    gueltig_sekunden: int


class GeraetPruefung(BaseModel):
    name: str
    bereich: str


# --- Benutzerverwaltung (Admin) --------------------------------------------

class BenutzerRead(BaseModel):
    id: int
    benutzername: str
    anzeigename: str
    email: Optional[str] = None
    rolle: Rolle
    aktiv: bool
    freigabe_ausstehend: bool
    hat_passwort: bool
    hat_pin: bool
    passwort_aendern: bool
    oidc_verknuepft: bool
    # Verknüpft mit einem anderen Anbieter als dem aktuell eingestellten
    oidc_veraltet: bool
    gesperrt_bis: Optional[datetime] = None
    angelegt_am: datetime
    letzte_anmeldung: Optional[datetime] = None


class BenutzerAnlegen(BaseModel):
    benutzername: str = Field(pattern=BENUTZERNAME_MUSTER)
    anzeigename: str = Field(min_length=1, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    rolle: Rolle = "mitarbeiter"
    # Startpasswort, muss bei der ersten Anmeldung geändert werden
    passwort: str = Field(min_length=1, max_length=256)


class BenutzerAendern(BaseModel):
    anzeigename: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    rolle: Optional[Rolle] = None
    aktiv: Optional[bool] = None
    # True gibt einen neuen OIDC-Benutzer frei (und aktiviert ihn)
    freigeben: Optional[bool] = None


class PasswortSetzen(BaseModel):
    passwort: str = Field(min_length=1, max_length=256)


class OidcUebernehmen(BaseModel):
    # Ausstehender OIDC-Benutzer, dessen Verknüpfung übernommen und der danach gelöscht wird
    von_benutzer_id: int


# --- Geräte (Admin) ----------------------------------------------------------

class GeraeteschluesselAnlegen(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    bereich: SchluesselBereich


class GeraeteschluesselAendern(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    aktiv: Optional[bool] = None


class GeraeteschluesselRead(BaseModel):
    id: int
    name: str
    bereich: str
    praefix: str
    aktiv: bool
    erstellt_am: datetime
    zuletzt_benutzt: Optional[datetime] = None


class GeraeteschluesselErzeugt(GeraeteschluesselRead):
    # Nur in dieser Antwort im Klartext, danach nie wieder
    schluessel: str


class GeraetesitzungRead(BaseModel):
    id: int
    name: str
    art: str
    angemeldet_von: Optional[str] = None
    bediener: Optional[str] = None
    erstellt_am: datetime
    zuletzt_gesehen: datetime
    laeuft_ab: datetime
    # None = Einstellung BEDIENER_TIMEOUT_MINUTEN, 0 = nie
    bediener_timeout_minuten: Optional[int] = None


class GeraetesitzungAendern(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    # Ausdrücklich null setzt auf die Einstellung zurück
    bediener_timeout_minuten: Optional[int] = Field(default=None, ge=0, le=24 * 60)
