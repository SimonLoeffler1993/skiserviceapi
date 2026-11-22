"""
Hashing von Passwörtern, PINs und Tokens sowie kurzlebige Werte im Speicher.

- Passwort und PIN: Argon2 (langsam, gegen Durchprobieren)
- Sitzungs-Tokens und Geräteschlüssel: lange Zufallswerte, gespeichert wird nur ihr SHA-256
- Tickets, OIDC-State und Einmalcodes liegen nur im Speicher (die API läuft mit einem Worker)
"""
import hashlib
import secrets
import threading
import time
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()
# Wird geprüft, wenn es den Benutzer nicht gibt, damit die Antwortzeit nichts verrät
_DUMMY_HASH = _hasher.hash("kein-benutzer")

# Präfixe der Tokens: Gerätesitzung, Bedienersitzung, Geräteschlüssel, Ticket
PRAEFIX_GERAET = "sg_"
PRAEFIX_BEDIENER = "sb_"
PRAEFIX_SCHLUESSEL = "gk_"
PRAEFIX_TICKET = "tk_"


def passwort_hash(passwort: str) -> str:
    return _hasher.hash(passwort)


def passwort_pruefen(gespeichert: str | None, eingabe: str) -> bool:
    """Prüft Passwort bzw. PIN gegen den gespeicherten Hash. Ohne Hash immer False (gleich langsam)."""
    try:
        return _hasher.verify(gespeichert or _DUMMY_HASH, eingabe) and gespeichert is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def braucht_neuen_hash(gespeichert: str) -> bool:
    try:
        return _hasher.check_needs_rehash(gespeichert)
    except InvalidHashError:
        return False


def token_erzeugen(praefix: str) -> str:
    return praefix + secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class KurzzeitSpeicher:
    """Werte mit Ablaufzeit im Speicher. Abgelaufene Einträge werden beim Zugriff aufgeräumt."""

    def __init__(self, sekunden: int):
        self.sekunden = sekunden
        self._werte: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def _aufraeumen(self, jetzt: float):
        for schluessel in [s for s, (ablauf, _) in self._werte.items() if ablauf < jetzt]:
            del self._werte[schluessel]

    def ablegen(self, schluessel: str, wert: Any):
        jetzt = time.monotonic()
        with self._lock:
            self._aufraeumen(jetzt)
            self._werte[schluessel] = (jetzt + self.sekunden, wert)

    def holen(self, schluessel: str) -> Any | None:
        jetzt = time.monotonic()
        with self._lock:
            self._aufraeumen(jetzt)
            eintrag = self._werte.get(schluessel)
            return eintrag[1] if eintrag else None

    def entnehmen(self, schluessel: str) -> Any | None:
        """Holt den Wert und löscht ihn: nur einmal verwendbar."""
        jetzt = time.monotonic()
        with self._lock:
            self._aufraeumen(jetzt)
            eintrag = self._werte.pop(schluessel, None)
            return eintrag[1] if eintrag else None


# Ticket für Zugriffe ohne Header (WebSocket, EventSource, PDF-Link): 2 Minuten, mehrfach nutzbar
tickets = KurzzeitSpeicher(120)
# OIDC: State bis zur Rückkehr vom Anbieter (10 Minuten), Einmalcode für die App (60 Sekunden)
oidc_states = KurzzeitSpeicher(600)
oidc_einmalcodes = KurzzeitSpeicher(60)
