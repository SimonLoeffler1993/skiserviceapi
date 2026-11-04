"""
Schlüsselpaare der Check-in-App: Der Browser verschlüsselt mit dem Public Key, nur die API kann entschlüsseln.
Der private Schlüssel verlässt die API über keine Schnittstelle.
"""
import base64
import hashlib
import threading
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from sqlalchemy.orm import Session

from app.models.checkin_schluessel import CheckinSchluessel

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
    return eintrag


def liste(db: Session) -> list[CheckinSchluessel]:
    return db.query(CheckinSchluessel).order_by(CheckinSchluessel.erstellt_am.desc()).all()


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
