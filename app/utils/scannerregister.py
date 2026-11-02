"""
Merkt sich, wann sich jeder Hardware-Skiscanner zuletzt gemeldet hat (Health-Check alle 30 s oder Scan).
Liegt nur im Arbeitsspeicher, die API muss daher mit einem Worker laufen.
"""
from datetime import datetime, timedelta, timezone

from app.schemas.scanner import ScannerGeraet, ScannerMeldung

# Zweimal das Meldeintervall der Firmware (30 s) plus Puffer
VERBUNDEN_ZEITRAUM = timedelta(seconds=75)
# Länger nicht gemeldete Scanner fallen aus der Liste
VERGESSEN_NACH = timedelta(hours=24)


class ScannerRegister:
    def __init__(self):
        self._geraete: dict[str, ScannerGeraet] = {}

    def melden(self, meldung: ScannerMeldung) -> None:
        bisher = self._geraete.get(meldung.name)
        daten = meldung.model_dump(exclude_unset=True)
        if bisher is not None:
            # Ein Scan liefert nur Name und Modus, Firmware usw. vom letzten Health-Check bleiben stehen
            daten = {**bisher.model_dump(include=set(ScannerMeldung.model_fields)), **daten}
        self._geraete[meldung.name] = ScannerGeraet(**daten, zuletzt=datetime.now(timezone.utc), verbunden=True)

    def liste(self) -> list[ScannerGeraet]:
        jetzt = datetime.now(timezone.utc)
        for name in [n for n, g in self._geraete.items() if jetzt - g.zuletzt > VERGESSEN_NACH]:
            del self._geraete[name]
        return [
            geraet.model_copy(update={"verbunden": jetzt - geraet.zuletzt < VERBUNDEN_ZEITRAUM})
            for geraet in sorted(self._geraete.values(), key=lambda g: g.name.lower())
        ]


scanner_register = ScannerRegister()
