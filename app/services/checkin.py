"""
Check-ins aus der Zwischendatenbank lesen, entschlüsseln und als Kunden übernehmen.
Klartext wird nie geloggt und nur beim Übernehmen in die Haupt-DB gespeichert.
Das Format steht in der README der Check-in-App.
"""
import base64
import json
import logging
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.crud import kunde as crud_kunde
from app.db.checkin import CheckIn, checkin_session, eingerichtet
from app.models.ort import Ort
from app.schemas.checkin import CheckinInhalt, CheckinKunde, CheckinRead, CheckinStatus
from app.schemas.kunde import SkiKundeSpeichern
from app.services.checkin_schluessel import privater_schluessel, schluessel_ids, utc

logger = logging.getLogger(__name__)

MAX_ANZAHL = 50


class CheckinNichtVerfuegbar(Exception):
    """Nicht eingerichtet oder Zwischendatenbank nicht erreichbar, die Meldung ist für das Center."""


class CheckinNichtGefunden(Exception):
    pass


class CheckinNichtLesbar(Exception):
    pass


class KundeNichtAngelegt(Exception):
    pass


@dataclass
class Uebernahme:
    kunde: object
    warnung: str | None = None


def _sitzung() -> Session:
    if not eingerichtet():
        raise CheckinNichtVerfuegbar("Der Check-in ist nicht eingerichtet.")
    return checkin_session()


def _db_fehler(fehler: SQLAlchemyError) -> CheckinNichtVerfuegbar:
    # Nur der Fehlername: Datenbankfehler können den ganzen Datensatz enthalten
    logger.error("Check-in-Datenbank: %s", type(fehler).__name__)
    return CheckinNichtVerfuegbar("Die Check-in-Datenbank ist nicht erreichbar.")


def _inhalt(db: Session, eintrag: CheckIn) -> CheckinKunde:
    """Entschlüsselt und prüft einen Datensatz, sonst CheckinNichtLesbar mit dem Grund."""
    if eintrag.version != 1:
        raise CheckinNichtLesbar(f"Unbekanntes Format (Version {eintrag.version}).")
    schluessel = privater_schluessel(db, eintrag.schluesselId)
    if schluessel is None:
        raise CheckinNichtLesbar("Der passende private Schlüssel fehlt.")
    try:
        aes_schluessel = schluessel.decrypt(
            base64.b64decode(eintrag.verschluesselterSchluessel),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
        klartext = AESGCM(aes_schluessel).decrypt(
            base64.b64decode(eintrag.iv),
            base64.b64decode(eintrag.daten),
            f"checkin:v1:{eintrag.schluesselId}".encode(),
        )
    except (ValueError, InvalidTag) as fehler:
        raise CheckinNichtLesbar("Der Datensatz lässt sich nicht entschlüsseln.") from fehler
    try:
        return CheckinInhalt.model_validate(json.loads(klartext)).kunde
    except (ValueError, ValidationError) as fehler:
        # Bewusst ohne Details: die Fehlermeldung enthielte Teile des Klartexts
        raise CheckinNichtLesbar("Der Inhalt ist ungültig.") from None


def liste(db: Session) -> list[CheckinRead]:
    """Offene Check-ins, neueste zuerst. Nicht lesbare werden markiert, nicht verworfen."""
    sitzung = _sitzung()
    try:
        eintraege = sitzung.scalars(select(CheckIn).order_by(CheckIn.erstelltAm.desc()).limit(MAX_ANZAHL)).all()
    except SQLAlchemyError as fehler:
        raise _db_fehler(fehler) from None
    finally:
        sitzung.close()
    ergebnis = []
    for eintrag in eintraege:
        try:
            ergebnis.append(CheckinRead(id=eintrag.id, erstellt_am=utc(eintrag.erstelltAm), lesbar=True, kunde=_inhalt(db, eintrag)))
        except CheckinNichtLesbar as fehler:
            ergebnis.append(CheckinRead(id=eintrag.id, erstellt_am=utc(eintrag.erstelltAm), lesbar=False, grund=str(fehler)))
    return ergebnis


def status(db: Session) -> CheckinStatus:
    if not eingerichtet():
        return CheckinStatus(eingerichtet=False, erreichbar=False)
    sitzung = checkin_session()
    try:
        offen = sitzung.scalar(select(func.count()).select_from(CheckIn)) or 0
        vorhanden = schluessel_ids(db)
        ohne = select(func.count()).select_from(CheckIn)
        if vorhanden:
            ohne = ohne.where(CheckIn.schluesselId.notin_(vorhanden))
        return CheckinStatus(eingerichtet=True, erreichbar=True, offen=offen, ohne_schluessel=sitzung.scalar(ohne) or 0)
    except SQLAlchemyError as fehler:
        _db_fehler(fehler)
        return CheckinStatus(eingerichtet=True, erreichbar=False)
    finally:
        sitzung.close()


def uebernehmen(db: Session, checkin_id: str) -> Uebernahme:
    """
    Legt den Kunden in der Haupt-DB an und löscht danach den Check-in.
    Die Sperre verhindert, dass zwei Geräte denselben Check-in doppelt übernehmen.
    """
    sitzung = _sitzung()
    try:
        eintrag = sitzung.scalars(select(CheckIn).where(CheckIn.id == checkin_id).with_for_update()).first()
    except SQLAlchemyError as fehler:
        sitzung.close()
        raise _db_fehler(fehler) from None
    try:
        if eintrag is None:
            raise CheckinNichtGefunden()
        daten = _inhalt(db, eintrag)

        warnung = None
        plz = int(daten.Plz) if daten.Plz else None
        # Die Haupt-DB kennt nur eingetragene Postleitzahlen, der Kunde soll daran nicht scheitern
        if plz is not None and db.get(Ort, plz) is None:
            warnung = f"PLZ {daten.Plz} {daten.Ort or ''} ist nicht bekannt und wurde nicht übernommen. Bitte beim Kunden ergänzen.".replace("  ", " ")
            plz = None
        antwort = crud_kunde.erfassen_kunde(db, SkiKundeSpeichern(
            Vorname=daten.Vorname, Nachname=daten.Nachname, Strasse=daten.Strasse, Plz=plz, Ort=daten.Ort,
            Tel=daten.Tel, Handy=daten.Handy, Email=daten.Email,
        ))
        if not antwort["success"]:
            raise KundeNichtAngelegt()
        kunde = crud_kunde.get_kunde(db, antwort["id"])

        try:
            sitzung.delete(eintrag)
            sitzung.commit()
        except SQLAlchemyError as fehler:
            _db_fehler(fehler)
            warnung = "Der Kunde ist angelegt, der Check-in konnte aber nicht gelöscht werden. Bitte verwerfen."
        return Uebernahme(kunde=kunde, warnung=warnung)
    finally:
        sitzung.close()


def verwerfen(checkin_id: str) -> None:
    sitzung = _sitzung()
    try:
        eintrag = sitzung.get(CheckIn, checkin_id)
        if eintrag is None:
            raise CheckinNichtGefunden()
        sitzung.delete(eintrag)
        sitzung.commit()
    except SQLAlchemyError as fehler:
        raise _db_fehler(fehler) from None
    finally:
        sitzung.close()
