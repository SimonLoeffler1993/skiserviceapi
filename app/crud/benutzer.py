"""Benutzerverwaltung für Admins. Fehler als ValueError (400) bzw. LookupError (404)."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.core import sicherheit
from app.models.benutzer import Bedienersitzung, Benutzer
from app.models.rechte import BenutzerGruppe
from app.schemas.benutzer import BenutzerAendern, BenutzerAnlegen
from app.crud import rechte as crud_rechte
from app.services import anmeldung, ereignisse


def benutzer_read(db: Session, benutzer: Benutzer) -> dict:
    return {
        **anmeldung.ich_benutzer(db, benutzer),
        "aktiv": bool(benutzer.Aktiv),
        "freigabe_ausstehend": bool(benutzer.Freigabe_Ausstehend),
        "gesperrt_bis": benutzer.Gesperrt_Bis if benutzer.Gesperrt_Bis and benutzer.Gesperrt_Bis > datetime.now() else None,
        "angelegt_am": benutzer.Angelegt_Am,
        "letzte_anmeldung": benutzer.Letzte_Anmeldung,
    }


def liste(db: Session) -> list[Benutzer]:
    # Ausstehende Freigaben zuerst
    return db.query(Benutzer).order_by(Benutzer.Freigabe_Ausstehend.desc(), Benutzer.Anzeigename).all()


def hole(db: Session, benutzer_id: int) -> Benutzer:
    benutzer = db.get(Benutzer, benutzer_id)
    if benutzer is None:
        raise LookupError("Benutzer nicht gefunden")
    return benutzer


def _name_frei(db: Session, benutzername: str, ausser_id: int | None = None) -> None:
    abfrage = db.query(Benutzer.ID).filter(Benutzer.Benutzername == benutzername)
    if ausser_id is not None:
        abfrage = abfrage.filter(Benutzer.ID != ausser_id)
    if abfrage.first():
        raise ValueError(f"Der Benutzername „{benutzername}“ ist schon vergeben.")


def _sitzungen_beenden(db: Session, benutzer_id: int) -> None:
    db.query(Bedienersitzung).filter(Bedienersitzung.Benutzer_ID == benutzer_id).delete()


def anlegen(db: Session, daten: BenutzerAnlegen) -> Benutzer:
    benutzername = daten.benutzername.strip()
    _name_frei(db, benutzername)
    anmeldung.passwort_regeln(daten.passwort)
    benutzer = Benutzer(
        Benutzername=benutzername,
        Anzeigename=daten.anzeigename.strip(),
        Email=(daten.email or "").strip() or None,
        Aktiv=True,
        Passwort_Hash=sicherheit.passwort_hash(daten.passwort),
        Passwort_Aendern=True,
        Angelegt_Am=datetime.now(),
    )
    db.add(benutzer)
    db.flush()
    crud_rechte.manuelle_gruppen_setzen(db, benutzer, daten.gruppen_ids)
    ereignisse.erfasse(db, "benutzer_angelegt", text=benutzer.Anzeigename,
                       daten={"benutzer_id": benutzer.ID})
    db.commit()
    return benutzer


def aendern(db: Session, benutzer_id: int, daten: BenutzerAendern) -> Benutzer:
    benutzer = hole(db, benutzer_id)
    felder = daten.model_dump(exclude_unset=True)
    aenderungen = []

    with crud_rechte.notzugang_schuetzen(db):
        if felder.get("anzeigename"):
            benutzer.Anzeigename = felder["anzeigename"].strip()
            aenderungen.append("Name")
        if "email" in felder:
            benutzer.Email = (felder["email"] or "").strip() or None
        if felder.get("gruppen_ids") is not None:
            if crud_rechte.manuelle_gruppen_setzen(db, benutzer, felder["gruppen_ids"]):
                aenderungen.append("Gruppen")
        if felder.get("freigeben"):
            benutzer.Freigabe_Ausstehend = False
            benutzer.Aktiv = True
            ereignisse.erfasse(db, "benutzer_freigegeben", text=benutzer.Anzeigename, daten={"benutzer_id": benutzer.ID})
        if "aktiv" in felder and felder["aktiv"] is not None:
            if bool(benutzer.Aktiv) != felder["aktiv"]:
                aenderungen.append("aktiviert" if felder["aktiv"] else "deaktiviert")
            benutzer.Aktiv = felder["aktiv"]
        if not benutzer.Aktiv:
            _sitzungen_beenden(db, benutzer.ID)
        if aenderungen:
            ereignisse.erfasse(db, "benutzer_geaendert", text=f"{benutzer.Anzeigename}: {', '.join(aenderungen)}",
                               daten={"benutzer_id": benutzer.ID})
    db.commit()
    return benutzer


def passwort_setzen(db: Session, benutzer_id: int, passwort: str) -> Benutzer:
    benutzer = hole(db, benutzer_id)
    anmeldung.passwort_regeln(passwort)
    benutzer.Passwort_Hash = sicherheit.passwort_hash(passwort)
    benutzer.Passwort_Aendern = True
    benutzer.Fehlversuche = 0
    benutzer.Gesperrt_Bis = None
    ereignisse.erfasse(db, "benutzer_geaendert", text=f"{benutzer.Anzeigename}: Passwort zurückgesetzt",
                       daten={"benutzer_id": benutzer.ID})
    db.commit()
    return benutzer


def pin_loeschen(db: Session, benutzer_id: int) -> Benutzer:
    benutzer = hole(db, benutzer_id)
    benutzer.Pin_Hash = None
    ereignisse.erfasse(db, "benutzer_geaendert", text=f"{benutzer.Anzeigename}: PIN gelöscht",
                       daten={"benutzer_id": benutzer.ID})
    db.commit()
    return benutzer


def entsperren(db: Session, benutzer_id: int) -> Benutzer:
    benutzer = hole(db, benutzer_id)
    benutzer.Fehlversuche = 0
    benutzer.Gesperrt_Bis = None
    db.commit()
    return benutzer


def oidc_loesen(db: Session, benutzer_id: int) -> Benutzer:
    benutzer = hole(db, benutzer_id)
    benutzer.Oidc_Issuer = benutzer.Oidc_Mandant = benutzer.Oidc_Kennung = None
    ereignisse.erfasse(db, "benutzer_geaendert", text=f"{benutzer.Anzeigename}: OIDC-Verknüpfung gelöst",
                       daten={"benutzer_id": benutzer.ID})
    db.commit()
    return benutzer


def oidc_uebernehmen(db: Session, benutzer_id: int, von_benutzer_id: int) -> Benutzer:
    """Die OIDC-Verknüpfung eines ausstehenden Benutzers geht auf einen vorhandenen über, der ausstehende wird gelöscht."""
    if benutzer_id == von_benutzer_id:
        raise ValueError("Ein Benutzer kann nicht von sich selbst übernehmen.")
    benutzer = hole(db, benutzer_id)
    von = hole(db, von_benutzer_id)
    if not von.Oidc_Issuer:
        raise ValueError(f"{von.Anzeigename} ist nicht mit OIDC verknüpft.")
    if not von.Freigabe_Ausstehend:
        raise ValueError("Übernommen werden können nur Benutzer, deren Freigabe aussteht.")
    issuer, mandant, kennung = von.Oidc_Issuer, von.Oidc_Mandant, von.Oidc_Kennung
    if not benutzer.Email and von.Email:
        benutzer.Email = von.Email
    # Über OIDC gekommene Gruppen gehen mit über
    oidc_gruppen = [m.Gruppe_ID for m in von.mitgliedschaften if m.Quelle == "oidc"]
    db.delete(von)
    db.flush()
    benutzer.Oidc_Issuer, benutzer.Oidc_Mandant, benutzer.Oidc_Kennung = issuer, mandant, kennung
    vorhanden = {m.Gruppe_ID for m in benutzer.mitgliedschaften}
    for gruppe_id in oidc_gruppen:
        if gruppe_id not in vorhanden:
            benutzer.mitgliedschaften.append(BenutzerGruppe(Gruppe_ID=gruppe_id, Quelle="oidc"))
    ereignisse.erfasse(db, "benutzer_geaendert", text=f"{benutzer.Anzeigename}: OIDC-Anmeldung von {von.Anzeigename} übernommen",
                       daten={"benutzer_id": benutzer.ID})
    db.commit()
    return benutzer


def loeschen(db: Session, benutzer_id: int, eigene_id: int | None) -> None:
    benutzer = hole(db, benutzer_id)
    if eigene_id is not None and benutzer.ID == eigene_id:
        raise ValueError("Das eigene Konto kann nicht gelöscht werden.")
    with crud_rechte.notzugang_schuetzen(db):
        ereignisse.erfasse(db, "benutzer_geloescht", text=f"{benutzer.Anzeigename} ({benutzer.Benutzername})")
        db.delete(benutzer)
    db.commit()
