"""
Schlüsselpaare der Check-in-App: Der Browser verschlüsselt mit dem Public Key, nur die API kann entschlüsseln.
Der private Schlüssel verlässt die API über keine Schnittstelle.
"""
import base64
import hashlib
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from sqlalchemy.orm import Session

from app.core.config import checkinPublicKeyOrdner
from app.models.checkin_schluessel import CheckinSchluessel

logger = logging.getLogger(__name__)

PUBLIC_KEY_DATEI = "checkin_public_key"

# Geladene Schlüssel: das Einlesen von RSA 4096 ist teuer, die Einträge ändern sich nie
_geladen: dict[str, RSAPrivateKey] = {}
_lock = threading.Lock()


def utc(zeit: datetime) -> datetime:
    """Die Datenbank speichert UTC ohne Zeitzone."""
    return zeit.replace(tzinfo=timezone.utc)


def erzeugen(db: Session) -> CheckinSchluessel:
    """Legt ein neues Schlüsselpaar an. Alte bleiben, damit ältere Datensätze lesbar bleiben."""
    schluessel = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    der = schluessel.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    eintrag = CheckinSchluessel(
        schluessel_id=hashlib.sha256(der).hexdigest(),
        public_key=base64.b64encode(der).decode(),
        private_key=schluessel.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ).decode(),
        erstellt_am=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(eintrag)
    db.commit()
    db.refresh(eintrag)
    public_key_veroeffentlichen(db)
    return eintrag


def liste(db: Session) -> list[CheckinSchluessel]:
    return db.query(CheckinSchluessel).order_by(CheckinSchluessel.erstellt_am.desc()).all()


def neuester(db: Session) -> CheckinSchluessel | None:
    return db.query(CheckinSchluessel).order_by(CheckinSchluessel.erstellt_am.desc()).first()


def public_key_automatisch() -> bool:
    """Ob die Check-in-App den Public Key über das gemeinsame Volume bekommt."""
    return bool(checkinPublicKeyOrdner)


def public_key_veroeffentlichen(db: Session) -> bool:
    """
    Schreibt den neuesten Public Key in den gemeinsamen Ordner. Über eine temporäre Datei und Umbenennen,
    damit die Check-in-App nie eine halbe Datei liest. Ein Fehler wird nur geloggt.
    """
    if not checkinPublicKeyOrdner:
        return False
    eintrag = neuester(db)
    if eintrag is None:
        return False
    try:
        os.makedirs(checkinPublicKeyOrdner, exist_ok=True)
        fd, temporaer = tempfile.mkstemp(dir=checkinPublicKeyOrdner, prefix=".checkin_public_key")
        with os.fdopen(fd, "w") as datei:
            datei.write(eintrag.public_key + "\n")
        # Die Check-in-App läuft unter einem anderen Benutzer und muss lesen können
        os.chmod(temporaer, 0o644)
        os.replace(temporaer, os.path.join(checkinPublicKeyOrdner, PUBLIC_KEY_DATEI))
        return True
    except OSError:
        logger.exception("Public Key konnte nicht nach %s geschrieben werden", checkinPublicKeyOrdner)
        return False


def public_key_bereitgestellt(db: Session) -> bool:
    """Ob der neueste Public Key in der Datei steht."""
    eintrag = neuester(db)
    if not checkinPublicKeyOrdner or eintrag is None:
        return False
    try:
        with open(os.path.join(checkinPublicKeyOrdner, PUBLIC_KEY_DATEI)) as datei:
            return datei.read().strip() == eintrag.public_key
    except OSError:
        return False


def beim_start(db: Session) -> None:
    """Mit gemeinsamem Ordner läuft die Einrichtung ohne Handgriffe: Fehlt ein Schlüssel, wird einer erzeugt."""
    if not checkinPublicKeyOrdner:
        return
    if neuester(db) is None:
        logger.info("Noch kein Check-in-Schlüssel vorhanden, erzeuge einen")
        erzeugen(db)
    else:
        public_key_veroeffentlichen(db)


def schluessel_ids(db: Session) -> set[str]:
    return {zeile[0] for zeile in db.query(CheckinSchluessel.schluessel_id).all()}


def privater_schluessel(db: Session, schluessel_id: str) -> RSAPrivateKey | None:
    with _lock:
        if schluessel_id in _geladen:
            return _geladen[schluessel_id]
    eintrag = db.get(CheckinSchluessel, schluessel_id)
    if eintrag is None:
        return None
    schluessel = serialization.load_pem_private_key(eintrag.private_key.encode(), password=None)
    with _lock:
        _geladen[schluessel_id] = schluessel
    return schluessel
