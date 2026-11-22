"""
Wer ruft die API auf?

Zugangsdaten (alle optional, solange die Pflicht in den Einstellungen aus ist):
- Authorization: Bearer sb_…  Bedienersitzung (Benutzer auf einem Gerät)
- Authorization: Bearer sg_…  Gerätesitzung ohne Bediener (Bedienerauswahl, PIN; nur dauerhaft angemeldete Geräte)
- X-Geraete-Schluessel: gk_…  Hardware-Scanner bzw. Kundenterminal
- ?ticket=tk_…               Kurzzeit-Ticket für WebSocket, EventSource und PDF-Links

Regel: Mitgeschickte Zugangsdaten werden immer geprüft, ungültige ergeben 401.
Fehlende Zugangsdaten sind nur erlaubt, solange ANMELDUNG_ERZWINGEN bzw. GERAETESCHLUESSEL_ERZWINGEN aus ist.

Der Zugriff wird in einer ContextVar abgelegt, damit Services (Ereignisprotokoll, angelegt_von)
den Benutzer kennen, ohne dass er durch alle Funktionen gereicht wird. Die Dependency muss dafür
async sein: Sync-Endpunkte laufen im Threadpool mit einer Kopie des Kontexts, in dem sie gesetzt wurde.
"""
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal

from fastapi import Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.core import rechte as rechte_mod
from app.core import sicherheit
from app.db.session import SessionLocal
from app.models.benutzer import Bedienersitzung, Benutzer, Geraeteschluessel, Geraetesitzung
from app.services import einstellungen

API_PRAEFIX = "/api/v1"

# Letzte_Aktivitaet / Zuletzt_Gesehen / Zuletzt_Benutzt höchstens so oft schreiben
_SCHREIB_ABSTAND = timedelta(seconds=60)


@dataclass(frozen=True)
class BenutzerInfo:
    id: int
    benutzername: str
    anzeigename: str
    # Summe der Rechte aus Gruppen -> Rollen (app/core/rechte.py), "*" = alle
    rechte: frozenset[str] = frozenset()

    def hat(self, recht: str) -> bool:
        return rechte_mod.hat(self.rechte, recht)


@dataclass(frozen=True)
class GeraetInfo:
    id: int
    name: str
    art: str
    timeout_minuten: int
    # False = persönliche Anmeldung, endet mit dem Bediener
    dauerhaft: bool = True


@dataclass(frozen=True)
class SchluesselInfo:
    id: int
    name: str
    bereich: str


@dataclass(frozen=True)
class Zugriff:
    benutzer: BenutzerInfo | None = None
    geraet: GeraetInfo | None = None
    bedienersitzung_id: int | None = None
    methode: str | None = None
    schluessel: SchluesselInfo | None = None
    # Über ein Ticket: nur für den Pfad, für den es ausgestellt wurde
    ticket_pfad: str | None = None

    @property
    def anonym(self) -> bool:
        return self.benutzer is None and self.geraet is None and self.schluessel is None

    @property
    def geraet_name(self) -> str | None:
        if self.geraet:
            return self.geraet.name
        if self.schluessel:
            return self.schluessel.name
        return None


ANONYM = Zugriff()

aktueller_zugriff: ContextVar[Zugriff] = ContextVar("aktueller_zugriff", default=ANONYM)


def aktueller_benutzer() -> BenutzerInfo | None:
    return aktueller_zugriff.get().benutzer


def aktueller_benutzer_id() -> int | None:
    benutzer = aktueller_benutzer()
    return benutzer.id if benutzer else None


class ZugriffFehler(HTTPException):
    pass


def _fehler(status: int, detail: str) -> ZugriffFehler:
    return ZugriffFehler(status_code=status, detail=detail)


def anmeldung_erzwungen() -> bool:
    return bool(einstellungen.hole("ANMELDUNG_ERZWINGEN"))


def geraeteschluessel_erzwungen() -> bool:
    return bool(einstellungen.hole("GERAETESCHLUESSEL_ERZWINGEN"))


def bediener_timeout(geraet: Geraetesitzung) -> int:
    if geraet.Bediener_Timeout_Minuten is not None:
        return geraet.Bediener_Timeout_Minuten
    return int(einstellungen.hole("BEDIENER_TIMEOUT_MINUTEN"))


def _geraet_info(geraet: Geraetesitzung) -> GeraetInfo:
    return GeraetInfo(id=geraet.ID, name=geraet.Name, art=geraet.Art, timeout_minuten=bediener_timeout(geraet),
                      dauerhaft=bool(geraet.Dauerhaft))


def _benutzer_info(db, benutzer: Benutzer) -> BenutzerInfo:
    from app.crud.rechte import rechte_von  # spät: crud -> services -> zugriff

    return BenutzerInfo(id=benutzer.ID, benutzername=benutzer.Benutzername,
                        anzeigename=benutzer.Anzeigename, rechte=rechte_von(db, benutzer.ID))


def _geraet_pruefen(db, geraet: Geraetesitzung | None, jetzt: datetime) -> Geraetesitzung:
    if geraet is None:
        raise _fehler(401, "anmeldung_noetig")
    if geraet.Laeuft_Ab < jetzt:
        db.delete(geraet)
        db.commit()
        raise _fehler(401, "anmeldung_noetig")
    if jetzt - geraet.Zuletzt_Gesehen > _SCHREIB_ABSTAND:
        # Gleitend: jede Nutzung verlängert die Sitzung
        geraet.Zuletzt_Gesehen = jetzt
        geraet.Laeuft_Ab = jetzt + timedelta(days=int(einstellungen.hole("GERAETESITZUNG_TAGE")))
    return geraet


def _bediener_ende(db, sitzung: Bedienersitzung | None, geraet: Geraetesitzung) -> ZugriffFehler:
    """Bediener weg: ein dauerhaftes Gerät wählt neu, eine persönliche Anmeldung endet ganz."""
    if sitzung is not None:
        db.delete(sitzung)
    if not geraet.Dauerhaft:
        db.delete(geraet)
        db.commit()
        return _fehler(401, "anmeldung_noetig")
    db.commit()
    return _fehler(401, "bediener_noetig")


def zugriff_aus_token(token: str) -> Zugriff:
    """Wertet ein Bearer-Token aus. Wirft 401 bei ungültigem oder abgelaufenem Token."""
    jetzt = datetime.now()
    hash_wert = sicherheit.token_hash(token)
    with SessionLocal() as db:
        if token.startswith(sicherheit.PRAEFIX_BEDIENER):
            sitzung = db.query(Bedienersitzung).filter(Bedienersitzung.Token_Hash == hash_wert).one_or_none()
            if sitzung is None:
                # Abgelaufen bzw. abgemeldet: das Gerät kann wieder einen Bediener wählen
                raise _fehler(401, "bediener_noetig")
            geraet = _geraet_pruefen(db, db.get(Geraetesitzung, sitzung.Geraetesitzung_ID), jetzt)
            timeout = bediener_timeout(geraet)
            if timeout and sitzung.Letzte_Aktivitaet + timedelta(minutes=timeout) < jetzt:
                raise _bediener_ende(db, sitzung, geraet)
            benutzer = db.get(Benutzer, sitzung.Benutzer_ID)
            if benutzer is None or not benutzer.darf_anmelden:
                raise _bediener_ende(db, sitzung, geraet)
            if jetzt - sitzung.Letzte_Aktivitaet > _SCHREIB_ABSTAND:
                sitzung.Letzte_Aktivitaet = jetzt
            ergebnis = Zugriff(benutzer=_benutzer_info(db, benutzer), geraet=_geraet_info(geraet),
                               bedienersitzung_id=sitzung.ID, methode=sitzung.Methode)
            db.commit()
            return ergebnis
        if token.startswith(sicherheit.PRAEFIX_GERAET):
            geraet = db.query(Geraetesitzung).filter(Geraetesitzung.Token_Hash == hash_wert).one_or_none()
            geraet = _geraet_pruefen(db, geraet, jetzt)
            if not geraet.Dauerhaft:
                # Persönliche Anmeldung ohne (gültigen) Bediener: keine Bedienerauswahl
                hat_bediener = db.query(Bedienersitzung.ID).filter(Bedienersitzung.Geraetesitzung_ID == geraet.ID).first()
                if not hat_bediener:
                    raise _bediener_ende(db, None, geraet)
            ergebnis = Zugriff(geraet=_geraet_info(geraet))
            db.commit()
            return ergebnis
    raise _fehler(401, "anmeldung_noetig")


def zugriff_aus_schluessel(schluessel: str) -> Zugriff:
    jetzt = datetime.now()
    with SessionLocal() as db:
        eintrag = (db.query(Geraeteschluessel)
                   .filter(Geraeteschluessel.Schluessel_Hash == sicherheit.token_hash(schluessel))
                   .one_or_none())
        if eintrag is None or not eintrag.Aktiv:
            raise _fehler(401, "geraeteschluessel_ungueltig")
        if eintrag.Zuletzt_Benutzt is None or jetzt - eintrag.Zuletzt_Benutzt > _SCHREIB_ABSTAND:
            eintrag.Zuletzt_Benutzt = jetzt
        ergebnis = Zugriff(schluessel=SchluesselInfo(id=eintrag.ID, name=eintrag.Name, bereich=eintrag.Bereich))
        db.commit()
        return ergebnis


def _pfad_passt(pfad: str, ticket_pfad: str) -> bool:
    voll = API_PRAEFIX + ticket_pfad
    return pfad.startswith(voll) if ticket_pfad.endswith("/") else pfad == voll


def zugriff_aus_ticket(ticket: str, pfad: str) -> Zugriff:
    """Ticket aus ?ticket=. Gilt nur für den Pfad (bzw. das Präfix mit / am Ende), für den es ausgestellt wurde."""
    eintrag: Zugriff | None = sicherheit.tickets.holen(ticket)
    if eintrag is None or not eintrag.ticket_pfad or not _pfad_passt(pfad, eintrag.ticket_pfad):
        raise _fehler(401, "ticket_ungueltig")
    return eintrag


def ticket_ausstellen(zugriff: Zugriff, pfad: str) -> str:
    ticket = sicherheit.token_erzeugen(sicherheit.PRAEFIX_TICKET)
    sicherheit.tickets.ablegen(ticket, replace(zugriff, ticket_pfad=pfad))
    return ticket


def _ermitteln(autorisierung: str | None, schluessel: str | None, ticket: str | None, pfad: str) -> Zugriff:
    if autorisierung:
        art, _, token = autorisierung.partition(" ")
        if art.lower() != "bearer" or not token.strip():
            raise _fehler(401, "anmeldung_noetig")
        return zugriff_aus_token(token.strip())
    if schluessel:
        return zugriff_aus_schluessel(schluessel.strip())
    if ticket:
        return zugriff_aus_ticket(ticket, pfad)
    return ANONYM


async def hole_zugriff(request: Request) -> Zugriff:
    """Dependency: ermittelt den Zugriff einmal je Anfrage und legt ihn in der ContextVar ab."""
    zugriff = getattr(request.state, "zugriff", None)
    if zugriff is None:
        zugriff = await run_in_threadpool(
            _ermitteln,
            request.headers.get("authorization"),
            request.headers.get("x-geraete-schluessel"),
            request.query_params.get("ticket"),
            request.url.path,
        )
        request.state.zugriff = zugriff
    aktueller_zugriff.set(zugriff)
    return zugriff


def darf_anonym_lesen() -> bool:
    """Ohne Anmeldung ansehen: im Übergang immer, sonst nur mit "Alles ansehen" der Gruppe "Ohne Anmeldung"."""
    if not anmeldung_erzwungen():
        return True
    from app.crud.rechte import gast_zugriff  # spät: crud -> services -> zugriff

    return gast_zugriff()[0]


def darf_anonym(recht: str) -> bool:
    """Recht ohne Anmeldung: im Übergang immer, sonst nur, wenn die Gruppe "Ohne Anmeldung" es hat."""
    if not anmeldung_erzwungen():
        return True
    from app.crud.rechte import gast_zugriff

    return rechte_mod.hat(gast_zugriff()[1], recht)


def _kein_benutzer(zugriff: Zugriff) -> None:
    """Gerät ohne Bediener bzw. Geräteschlüssel: nie wie "ohne Anmeldung" behandeln."""
    if zugriff.geraet is not None:
        # Gerät angemeldet, aber kein Bediener gewählt
        raise _fehler(401, "bediener_noetig")
    if zugriff.schluessel is not None:
        raise _fehler(403, "geraeteschluessel_nicht_erlaubt")


def _benutzer_verlangen(zugriff: Zugriff) -> None:
    """Lesen: angemeldet, oder ohne Anmeldung, wenn Ansehen ohne Anmeldung erlaubt ist."""
    if zugriff.benutzer is not None:
        return
    _kein_benutzer(zugriff)
    if not darf_anonym_lesen():
        raise _fehler(401, "anmeldung_noetig")


async def angemeldet(zugriff: Zugriff = Depends(hole_zugriff)) -> Zugriff:
    """Lesen. Ohne Anmeldung im Übergang bzw. mit "Alles ansehen" der Gruppe "Ohne Anmeldung"."""
    _benutzer_verlangen(zugriff)
    return zugriff


def pruefe_recht(recht: str, zugriff: Zugriff | None = None) -> None:
    """
    Für Prüfungen im Handler, z.B. wenn nur eine Variante einer Route ein Recht braucht.
    Ohne Anmeldung im Übergang bzw. wenn die Gruppe "Ohne Anmeldung" das Recht hat.
    """
    zugriff = zugriff or aktueller_zugriff.get()
    if zugriff.benutzer is not None:
        if not zugriff.benutzer.hat(recht):
            raise _fehler(403, "recht_fehlt")
        return
    _kein_benutzer(zugriff)
    if not darf_anonym(recht):
        raise _fehler(401, "anmeldung_noetig")


def recht(name: str):
    """Dependency: mit diesem Recht (app/core/rechte.py). Ohne Anmeldung reicht das Recht der Gastgruppe."""
    if name not in rechte_mod.RECHTE:
        raise ValueError(f"Unbekanntes Recht: {name}")

    async def pruefen(zugriff: Zugriff = Depends(hole_zugriff)) -> Zugriff:
        pruefe_recht(name, zugriff)
        return zugriff

    return pruefen


def lesen_oder_recht(name: str):
    """Dependency: lesen dürfen oder dieses Recht haben (z.B. Quittungs-PDF auch nur mit Kassenrecht)."""
    async def pruefen(zugriff: Zugriff = Depends(hole_zugriff)) -> Zugriff:
        if zugriff.benutzer is None and zugriff.geraet is None and zugriff.schluessel is None \
                and not darf_anonym_lesen() and darf_anonym(name):
            return zugriff
        _benutzer_verlangen(zugriff)
        return zugriff

    return pruefen


_LESEND = {"GET", "HEAD", "OPTIONS"}


def _pfad(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


def schreibrecht(name: str, ausser: tuple[str, ...] = ()):
    """
    Router-Dependency: Lesen wie angemeldet(), Schreiben (POST/PUT/PATCH/DELETE) nur mit diesem Recht.
    ausser: Endungen von Routen-Pfaden, die stattdessen ein eigenes Recht an der Route haben (z.B. "/preise").
    """
    if name not in rechte_mod.RECHTE:
        raise ValueError(f"Unbekanntes Recht: {name}")

    async def pruefen(request: Request, zugriff: Zugriff = Depends(hole_zugriff)) -> Zugriff:
        if request.method in _LESEND:
            _benutzer_verlangen(zugriff)
        elif not _pfad(request).endswith(ausser or ("\0",)):
            # Schreiben ohne Anmeldung braucht nur das Recht, nicht "Alles ansehen"
            pruefe_recht(name, zugriff)
        return zugriff

    return pruefen


def angemeldet_ausser(ausser: tuple[str, ...]):
    """Router-Dependency wie angemeldet(), außer für Routen mit diesen Pfad-Endungen (eigene Prüfung an der Route)."""
    async def pruefen(request: Request, zugriff: Zugriff = Depends(hole_zugriff)) -> Zugriff:
        if not _pfad(request).endswith(ausser):
            _benutzer_verlangen(zugriff)
        return zugriff

    return pruefen


async def benutzer_noetig(zugriff: Zugriff = Depends(hole_zugriff)) -> Zugriff:
    """Immer ein angemeldeter Benutzer, auch im Übergang (z.B. „Mein Konto“)."""
    if zugriff.benutzer is None:
        raise _fehler(401, "bediener_noetig" if zugriff.geraet else "anmeldung_noetig")
    return zugriff


async def nur_geraetesitzung(zugriff: Zugriff = Depends(hole_zugriff)) -> Zugriff:
    """Ein dauerhaft angemeldetes Gerät, mit oder ohne Bediener (Bedienerauswahl, PIN)."""
    if zugriff.geraet is None:
        raise _fehler(401, "anmeldung_noetig")
    if not zugriff.geraet.dauerhaft:
        raise _fehler(403, "geraet_nicht_dauerhaft")
    return zugriff


def geraet_oder_angemeldet(bereich: Literal["scanner", "terminal"], benutzer_recht: str | None = None):
    """
    Geräteschlüssel des Bereichs oder ein angemeldeter Benutzer (mit benutzer_recht, falls angegeben).
    Ohne Zugangsdaten nur, solange GERAETESCHLUESSEL_ERZWINGEN aus ist; beim Kundenterminal
    (Kundendaten) zusätzlich nur, wenn das ohne Anmeldung erlaubt ist (Übergang bzw. Gastgruppe).
    """
    async def pruefen(zugriff: Zugriff = Depends(hole_zugriff)) -> Zugriff:
        if zugriff.schluessel is not None:
            if zugriff.schluessel.bereich != bereich:
                raise _fehler(403, "geraeteschluessel_nicht_erlaubt")
            return zugriff
        if zugriff.benutzer is not None:
            if benutzer_recht:
                pruefe_recht(benutzer_recht, zugriff)
            return zugriff
        if zugriff.geraet is not None:
            raise _fehler(401, "bediener_noetig")
        if geraeteschluessel_erzwungen():
            raise _fehler(401, "geraeteschluessel_noetig")
        # Kundenterminal ohne Schlüssel: nur, wenn ohne Anmeldung erlaubt (Übergang bzw. Gastgruppe)
        if bereich == "terminal" and not (darf_anonym(benutzer_recht) if benutzer_recht else darf_anonym_lesen()):
            raise _fehler(401, "geraeteschluessel_noetig")
        return zugriff

    return pruefen
