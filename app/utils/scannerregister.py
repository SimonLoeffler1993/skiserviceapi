"""
Merkt sich, wann sich jeder Hardware-Skiscanner zuletzt gemeldet hat (Health-Check alle 30 s oder Scan),
und ob im Center ein Firmware-Update für ihn angestoßen wurde.
Liegt nur im Arbeitsspeicher, die API muss daher mit einem Worker laufen.
"""
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.schemas.scanner import ScannerGeraet, ScannerMeldung

# Zweimal das Meldeintervall der Firmware (30 s) plus Puffer
VERBUNDEN_ZEITRAUM = timedelta(seconds=75)
# Länger nicht gemeldete Scanner fallen aus der Liste
VERGESSEN_NACH = timedelta(hours=24)


class ScannerUnbekannt(Exception):
    pass


class UpdateNichtMoeglich(Exception):
    pass


class ScannerRegister:
    def __init__(self):
        self._geraete: dict[str, ScannerGeraet] = {}
        # Scanner, denen das Update bei der nächsten Meldung noch mitgeteilt werden muss
        self._update_offen: set[str] = set()
        # /melden läuft im Threadpool, /scan im Event-Loop
        self._sperre = Lock()

    def melden(self, meldung: ScannerMeldung, health_check: bool = False, schluessel: str | None = None) -> bool:
        """
        Trägt die Meldung ein. Gibt True zurück, wenn der Scanner jetzt ein Update starten soll:
        nur beim Health-Check und nur einmal je Anforderung.
        """
        with self._sperre:
            bisher = self._geraete.get(meldung.name)
            daten = meldung.model_dump(exclude_unset=True)
            angefordert = None
            if bisher is not None:
                # Ein Scan liefert nur Name und Modus, Firmware usw. vom letzten Health-Check bleiben stehen
                daten = {**bisher.model_dump(include=set(ScannerMeldung.model_fields)), **daten}
                angefordert = bisher.update_angefordert

            update_starten = False
            if health_check:
                if meldung.name in self._update_offen:
                    self._update_offen.discard(meldung.name)
                    update_starten = True
                elif angefordert is not None and (
                    meldung.update_status or (bisher is not None and meldung.firmware != bisher.firmware)
                ):
                    # Der Scanner hat reagiert: ab jetzt zählt sein eigener Stand
                    angefordert = None

            self._geraete[meldung.name] = ScannerGeraet(
                **daten, zuletzt=datetime.now(timezone.utc), verbunden=True, update_angefordert=angefordert,
                schluessel=schluessel,
            )
            return update_starten

    def update_anfordern(self, name: str) -> ScannerGeraet:
        with self._sperre:
            jetzt = datetime.now(timezone.utc)
            geraet = self._geraete.get(name)
            if geraet is None:
                raise ScannerUnbekannt(name)
            if jetzt - geraet.zuletzt >= VERBUNDEN_ZEITRAUM:
                raise UpdateNichtMoeglich("Der Scanner ist nicht verbunden.")
            if not geraet.update_faehig:
                raise UpdateNichtMoeglich(
                    "Die Firmware dieses Scanners kann sich noch nicht selbst aktualisieren. "
                    "Bitte einmalig über den Webflasher oder die Konfigurationsseite des Scanners aktualisieren."
                )
            geraet = geraet.model_copy(update={"update_angefordert": jetzt})
            self._geraete[name] = geraet
            self._update_offen.add(name)
            return geraet

    def liste(self) -> list[ScannerGeraet]:
        with self._sperre:
            jetzt = datetime.now(timezone.utc)
            for name in [n for n, g in self._geraete.items() if jetzt - g.zuletzt > VERGESSEN_NACH]:
                del self._geraete[name]
                self._update_offen.discard(name)
            return [
                geraet.model_copy(update={"verbunden": jetzt - geraet.zuletzt < VERBUNDEN_ZEITRAUM})
                for geraet in sorted(self._geraete.values(), key=lambda g: g.name.lower())
            ]


scanner_register = ScannerRegister()
