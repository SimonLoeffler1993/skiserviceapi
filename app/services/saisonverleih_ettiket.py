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


def etiketten_liste(verleih: SaisonVerleih) -> list[dict]:
    """
    Ein Etikett je Leihski und je Leihschuh, damit das Material in der Werkstatt eindeutig zugeordnet werden kann.
    Schlüssel z.B. "12-ski" oder "12-schuh" (Material-ID und Teil).
    """
    kunde = kunden_name(verleih.Kunde.Vorname, verleih.Kunde.Nachname) if verleih.Kunde else ""
    rueckgabe = _rueckgabe(verleih)
    info = f"{verleih.Name} · bis {rueckgabe}" if rueckgabe else verleih.Name
    liste = []
    for material in verleih.Material:
        # QR-Code führt zur Materialzeile, die in der Ansicht hervorgehoben wird
        url = f"{appHost()}/saisonverleih/anzeigen/{verleih.ID}?material={material.ID}"
        fahrer = (material.SkiFahrerName or "").strip() or None
        name = fahrer or kunde or verleih.Name
        if material.skinr:
            liste.append({
                "Schluessel": f"{material.ID}-ski",
                "Name": name,
                "Fahrer": fahrer,
                "Teil": f"SKI {material.skinr}",
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
                "Teil": f"SCHUH {schuh.SchuhNr}" + (f" · {groesse}" if groesse else ""),
                "Info": info,
                "Url": url,
                "Bindung": f"Sohle {sohle}mm" if sohle else None,
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
        raise EttiketFehler("Keine Etiketten zum Drucken, der Verleih hat weder Ski noch Schuhe.")

    drucker = SkiEttiket()
    for eintrag in liste:
        drucker.verleihEttiket(eintrag["Name"], eintrag["Teil"], eintrag["Info"], eintrag["Url"], eintrag["Bindung"])
    logger.info("%s Verleih-Etiketten für %s erstellt, jetzt kommt der Druck", len(liste), verleih.Name)
    if not drucker.drucken():
        raise EttiketFehler("Drucker nicht erreichbar, bitte die Etikettendrucker-Einstellungen prüfen.")
    return len(liste)
