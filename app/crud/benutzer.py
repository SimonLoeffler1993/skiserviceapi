"""Benutzerverwaltung für Admins. Fehler als ValueError (400) bzw. LookupError (404)."""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import sicherheit
from app.models.benutzer import Bedienersitzung, Benutzer
from app.schemas.benutzer import BenutzerAendern, BenutzerAnlegen
from app.services import anmeldung, ereignisse


def benutzer_read(benutzer: Benutzer) -> dict:
    return {
        **anmeldung.ich_benutzer(benutzer),
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


def _ist_tragender_admin(benutzer: Benutzer) -> bool:
    """Ein Admin, mit dem man sich jederzeit anmelden kann (Notzugang ohne OIDC)."""
    return benutzer.Rolle == "admin" and benutzer.Aktiv and not benutzer.Freigabe_Ausstehend and bool(benutzer.Passwort_Hash)


def _letzten_admin_schuetzen(db: Session, benutzer: Benutzer) -> None:
    """Wirft, wenn nach der Änderung kein Admin mit Passwort mehr übrig wäre."""
    andere = (db.query(func.count(Benutzer.ID))
              .filter(Benutzer.ID != benutzer.ID, Benutzer.Rolle == "admin", Benutzer.Aktiv.is_(True),
                      Benutzer.Freigabe_Ausstehend.is_(False), Benutzer.Passwort_Hash.is_not(None))
              .scalar())
    if not andere:
        raise ValueError("Es muss mindestens ein aktiver Admin mit Passwort bleiben.")


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
        Rolle=daten.rolle,
        Aktiv=True,
        Passwort_Hash=sicherheit.passwort_hash(daten.passwort),
        Passwort_Aendern=True,
        Angelegt_Am=datetime.now(),
    )
    db.add(benutzer)
    db.flush()
    ereignisse.erfasse(db, "benutzer_angelegt", text=f"{benutzer.Anzeigename} ({benutzer.Rolle})",
                       daten={"benutzer_id": benutzer.ID})
    db.commit()
    return benutzer


def aendern(db: Session, benutzer_id: int, daten: BenutzerAendern) -> Benutzer:
    benutzer = hole(db, benutzer_id)
    felder = daten.model_dump(exclude_unset=True)
    vorher_tragend = _ist_tragender_admin(benutzer)
    aenderungen = []

    if felder.get("anzeigename"):
        benutzer.Anzeigename = felder["anzeigename"].strip()
        aenderungen.append("Name")
    if "email" in felder:
        benutzer.Email = (felder["email"] or "").strip() or None
    if felder.get("rolle"):
        if benutzer.Rolle != felder["rolle"]:
            aenderungen.append(f"Rolle {felder['rolle']}")
        benutzer.Rolle = felder["rolle"]
    if felder.get("freigeben"):
        benutzer.Freigabe_Ausstehend = False
        benutzer.Aktiv = True
        ereignisse.erfasse(db, "benutzer_freigegeben", text=benutzer.Anzeigename, daten={"benutzer_id": benutzer.ID})
    if "aktiv" in felder and felder["aktiv"] is not None:
        if bool(benutzer.Aktiv) != felder["aktiv"]:
            aenderungen.append("aktiviert" if felder["aktiv"] else "deaktiviert")
        benutzer.Aktiv = felder["aktiv"]

    if vorher_tragend and not _ist_tragender_admin(benutzer):
        _letzten_admin_schuetzen(db, benutzer)
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
    db.delete(von)
    db.flush()
    benutzer.Oidc_Issuer, benutzer.Oidc_Mandant, benutzer.Oidc_Kennung = issuer, mandant, kennung
    ereignisse.erfasse(db, "benutzer_geaendert", text=f"{benutzer.Anzeigename}: OIDC-Anmeldung von {von.Anzeigename} übernommen",
                       daten={"benutzer_id": benutzer.ID})
    db.commit()
    return benutzer


def loeschen(db: Session, benutzer_id: int, eigene_id: int | None) -> None:
    benutzer = hole(db, benutzer_id)
    if eigene_id is not None and benutzer.ID == eigene_id:
        raise ValueError("Das eigene Konto kann nicht gelöscht werden.")
    if _ist_tragender_admin(benutzer):
        _letzten_admin_schuetzen(db, benutzer)
    ereignisse.erfasse(db, "benutzer_geloescht", text=f"{benutzer.Anzeigename} ({benutzer.Benutzername})")
    db.delete(benutzer)
    db.commit()
