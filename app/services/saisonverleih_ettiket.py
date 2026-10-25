import logging

from app.models.saisonverleih import SaisonVerleih
from app.services.skiserviceauftrag import appHost, bindungsdaten_zeile, kunden_name
from app.utils.skiEttiket import SkiEttiket

logger = logging.getLogger(__name__)


class EttiketFehler(Exception):
    pass


def _groesse(wert: float | None) -> str:
    if wert is None:
        return ""
    return str(int(wert)) if float(wert).is_integer() else str(wert).replace(".", ",")


def _rueckgabe(verleih: SaisonVerleih) -> str | None:
    """Tagesverleih: Ende des Zeitraums, Saisonverleih: Saisonende."""
    ende = verleih.Ende_Am if verleih.Art == "tag" else (verleih.Saison.Ende if verleih.Saison else None)
    return ende.strftime("%d.%m.%y") if ende else None


def material_nummern(verleih: SaisonVerleih) -> dict[int, int]:
    """Laufende Nummer je Materialzeile im Verleih (1, 2, ...), in Erfassungsreihenfolge."""
    return {material.ID: nr for nr, material in enumerate(sorted(verleih.Material, key=lambda m: m.ID), start=1)}


def etiketten_liste(verleih: SaisonVerleih) -> list[dict]:
    """
    Ein Etikett je Leihski und je Leihschuh, damit das Material in der Werkstatt eindeutig zugeordnet werden kann.
    Materialzeilen ohne Ski und Schuh (nur Preis oder Stock) bekommen ebenfalls eines.
    Oben steht der Kunde, darunter Teil, Fahrer und laufende Nummer der Zeile (siehe material_nummern),
    z.B. "SKI Simon #1", "SCHUH #2 · 28,5", "STOCK #3" oder nur "#4".
    Schlüssel z.B. "12-ski", "12-schuh" oder "12-material" (Material-ID und Teil).
    """
    kunde = kunden_name(verleih.Kunde.Vorname, verleih.Kunde.Nachname) if verleih.Kunde else ""
    rueckgabe = _rueckgabe(verleih)
    info = f"{verleih.Name} · bis {rueckgabe}" if rueckgabe else verleih.Name
    nummern = material_nummern(verleih)
    liste = []
    for material in verleih.Material:
        # QR-Code führt zur Materialzeile, die in der Ansicht hervorgehoben wird
        url = f"{appHost()}/saisonverleih/anzeigen/{verleih.ID}?material={material.ID}"
        fahrer = (material.SkiFahrerName or "").strip() or None
        name = kunde or verleih.Name
        nr = nummern[material.ID]
        bezeichnung = fahrer or f"Ausrüstung #{nr}"
        # Statt Ski-/Schuhnummer: Fahrer (falls vorhanden) und laufende Nummer, z.B. "Simon #1" oder "#2"
        kennung = f"{fahrer} #{nr}" if fahrer else f"#{nr}"
        if material.skinr:
            liste.append({
                "Schluessel": f"{material.ID}-ski",
                "Name": name,
                "Fahrer": fahrer,
                "Bezeichnung": bezeichnung,
                "Teil": f"SKI {kennung}",
                "Info": info,
                "Url": url,
                "Bindung": bindungsdaten_zeile(material.bindungsdaten),
            })
        if material.Schuh:
            schuh = material.Schuh
            groesse = _groesse(schuh.Groese)
            sohle = material.bindungsdaten.Sohle if material.bindungsdaten and material.bindungsdaten.Sohle else schuh.Sohle
            liste.append({
                "Schluessel": f"{material.ID}-schuh",
                "Name": name,
                "Fahrer": fahrer,
                "Bezeichnung": bezeichnung,
                "Teil": f"SCHUH {kennung}" + (f" · {groesse}" if groesse else ""),
                "Info": info,
                "Url": url,
                "Bindung": f"Sohle {sohle}mm" if sohle else None,
            })
        if not material.skinr and not material.Schuh:
            liste.append({
                "Schluessel": f"{material.ID}-material",
                "Name": name,
                "Fahrer": fahrer,
                "Bezeichnung": bezeichnung,
                "Teil": f"STOCK {kennung}" if material.Stock else kennung,
                "Info": info,
                "Url": url,
                "Bindung": bindungsdaten_zeile(material.bindungsdaten),
            })
    return liste


def verleih_ettiketten_drucken(verleih: SaisonVerleih, schluessel: list[str] | None = None) -> int:
    """Druckt die gewählten Etiketten (ohne Auswahl alle) und gibt die Anzahl zurück."""
    liste = etiketten_liste(verleih)
    if schluessel is not None:
        bekannt = {eintrag["Schluessel"] for eintrag in liste}
        unbekannt = [s for s in schluessel if s not in bekannt]
        if unbekannt:
            raise ValueError(f"Unbekannte Etiketten: {', '.join(unbekannt)}")
        liste = [eintrag for eintrag in liste if eintrag["Schluessel"] in schluessel]
    if not liste:
        raise EttiketFehler("Keine Etiketten zum Drucken, der Verleih hat kein Material.")

    drucker = SkiEttiket()
    for eintrag in liste:
        drucker.verleihEttiket(eintrag["Name"], eintrag["Teil"], eintrag["Info"], eintrag["Url"], eintrag["Bindung"])
    logger.info("%s Verleih-Etiketten für %s erstellt, jetzt kommt der Druck", len(liste), verleih.Name)
    if not drucker.drucken():
        raise EttiketFehler("Drucker nicht erreichbar, bitte die Etikettendrucker-Einstellungen prüfen.")
    return len(liste)
