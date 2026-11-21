"""
Rollen, Gruppen und Mitgliedschaften. Fehler als ValueError (400) bzw. LookupError (404).

Notzugang: Es muss immer ein aktiver Benutzer mit Passwort bleiben, der Benutzer verwalten darf
(sonst könnte sich niemand mehr Rechte geben, z.B. wenn der OIDC-Anbieter ausfällt).
"""
import logging
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rechte import ADMIN_GRUPPE, ALLE_RECHTE, MITARBEITER_RECHTE, RECHTE, SYSTEMROLLE, VERWALTUNGSRECHT
from app.models.benutzer import Benutzer
from app.models.rechte import BenutzerGruppe, Gruppe, GruppeRolle, Rolle, RolleRecht
from app.services import ereignisse

logger = logging.getLogger(__name__)

NOTZUGANG_TEXT = "Es muss mindestens ein aktiver Benutzer mit Passwort bleiben, der Benutzer verwalten darf."

GAST_GRUPPE = "Ohne Anmeldung"
# Ohne Anmeldung nie: sonst könnte sich jeder im Netz selbst zum Admin machen
GAST_VERBOTEN = {ALLE_RECHTE, VERWALTUNGSRECHT}
GAST_VERBOTEN_TEXT = "Die Gruppe „Ohne Anmeldung“ darf weder alle Rechte noch „Benutzer verwalten“ bekommen."


# --- Gruppe "Ohne Anmeldung" -------------------------------------------------------

_gast_cache: tuple[bool, frozenset[str]] | None = None


def gast_cache_leeren() -> None:
    global _gast_cache
    _gast_cache = None


def gast_gruppe(db: Session) -> Gruppe:
    """Systemgruppe für Aufrufe ohne Anmeldung; legt sie an, falls sie fehlt (ohne Commit)."""
    gruppe = db.query(Gruppe).filter(Gruppe.Gast.is_(True)).first()
    if gruppe is None:
        name = GAST_GRUPPE if not db.query(Gruppe.ID).filter(Gruppe.Name == GAST_GRUPPE).first() else f"{GAST_GRUPPE} (System)"
        gruppe = Gruppe(Name=name, Beschreibung="Rechte für alle, die nicht angemeldet sind", Gast=True, Lesen=False,
                        Angelegt_Am=datetime.now())
        db.add(gruppe)
        db.flush()
    return gruppe


def gast_zugriff() -> tuple[bool, frozenset[str]]:
    """(alles ansehen, Rechte) für Aufrufe ohne Anmeldung, im Speicher zwischengespeichert."""
    global _gast_cache
    if _gast_cache is None:
        from app.db.session import SessionLocal

        try:
            with SessionLocal() as db:
                gruppe = db.query(Gruppe).filter(Gruppe.Gast.is_(True)).first()
                if gruppe is None:
                    _gast_cache = (False, frozenset())
                else:
                    rechte = frozenset(r.Recht for rolle in gruppe.rollen for r in rolle.rechte) - GAST_VERBOTEN
                    _gast_cache = (bool(gruppe.Lesen), rechte)
        except Exception:
            logger.exception("Rechte ohne Anmeldung nicht lesbar")
            return (False, frozenset())
    return _gast_cache


def _gast_rollen_pruefen(rollen: list[Rolle]) -> None:
    for rolle in rollen:
        if rolle.System or GAST_VERBOTEN & {r.Recht for r in rolle.rechte}:
            raise ValueError(GAST_VERBOTEN_TEXT)


# --- Rechte eines Benutzers -----------------------------------------------------

def rechte_von(db: Session, benutzer_id: int) -> frozenset[str]:
    """Summe der Rechte aller Rollen aller Gruppen des Benutzers."""
    zeilen = db.execute(
        select(RolleRecht.Recht)
        .join(GruppeRolle, GruppeRolle.Rolle_ID == RolleRecht.Rolle_ID)
        .join(BenutzerGruppe, BenutzerGruppe.Gruppe_ID == GruppeRolle.Gruppe_ID)
        .where(BenutzerGruppe.Benutzer_ID == benutzer_id)
    ).scalars().all()
    return frozenset(zeilen)


def rechte_liste(rechte: frozenset[str]) -> list[str]:
    """Für die Frontends: "*" wird zu allen bekannten Rechten (plus "*")."""
    if ALLE_RECHTE in rechte:
        return [ALLE_RECHTE, *RECHTE.keys()]
    return sorted(r for r in rechte if r in RECHTE)


def gruppen_von(benutzer: Benutzer, db: Session) -> list[dict]:
    namen = {g.ID: g.Name for g in db.query(Gruppe.ID, Gruppe.Name).all()}
    return sorted(({"id": m.Gruppe_ID, "name": namen.get(m.Gruppe_ID, "?"), "quelle": m.Quelle}
                   for m in benutzer.mitgliedschaften), key=lambda g: g["name"].lower())


# --- Notzugang -------------------------------------------------------------------

def notzugang_vorhanden(db: Session, ausser_benutzer_id: int | None = None) -> bool:
    abfrage = (
        select(func.count(func.distinct(Benutzer.ID)))
        .join(BenutzerGruppe, BenutzerGruppe.Benutzer_ID == Benutzer.ID)
        .join(GruppeRolle, GruppeRolle.Gruppe_ID == BenutzerGruppe.Gruppe_ID)
        .join(RolleRecht, RolleRecht.Rolle_ID == GruppeRolle.Rolle_ID)
        .where(Benutzer.Aktiv.is_(True), Benutzer.Freigabe_Ausstehend.is_(False), Benutzer.Passwort_Hash.is_not(None),
               RolleRecht.Recht.in_([ALLE_RECHTE, VERWALTUNGSRECHT]))
    )
    if ausser_benutzer_id is not None:
        abfrage = abfrage.where(Benutzer.ID != ausser_benutzer_id)
    return (db.execute(abfrage).scalar() or 0) > 0


@contextmanager
def notzugang_schuetzen(db: Session):
    """
    Um eine Änderung legen: gab es vorher einen Notzugang und danach nicht mehr, wird zurückgerollt.
    Ohne Notzugang vorher (frische Installation, Übergang) wird nichts blockiert.
    """
    vorher = notzugang_vorhanden(db)
    yield
    db.flush()
    if vorher and not notzugang_vorhanden(db):
        db.rollback()
        raise ValueError(NOTZUGANG_TEXT)


# --- Systemrolle und Admin-Gruppe ------------------------------------------------

def admin_gruppe(db: Session) -> Gruppe:
    """Gruppe mit der Systemrolle; legt Rolle und Gruppe an, falls sie fehlen (ohne Commit)."""
    rolle = db.query(Rolle).filter(Rolle.System.is_(True)).first()
    if rolle is None:
        rolle = db.query(Rolle).filter(Rolle.Name == SYSTEMROLLE).first()
        if rolle is None:
            rolle = Rolle(Name=SYSTEMROLLE, Beschreibung="Alle Rechte", Angelegt_Am=datetime.now())
            db.add(rolle)
        rolle.System = True
        rolle.rechte = [RolleRecht(Recht=ALLE_RECHTE)]
        db.flush()
    gruppe = (db.query(Gruppe).join(GruppeRolle, GruppeRolle.Gruppe_ID == Gruppe.ID)
              .filter(GruppeRolle.Rolle_ID == rolle.ID).order_by(Gruppe.ID).first())
    if gruppe is None:
        gruppe = db.query(Gruppe).filter(Gruppe.Name == ADMIN_GRUPPE).first() or Gruppe(
            Name=ADMIN_GRUPPE, Beschreibung="Vollzugriff", Angelegt_Am=datetime.now())
        db.add(gruppe)
        db.flush()
        db.add(GruppeRolle(Gruppe_ID=gruppe.ID, Rolle_ID=rolle.ID))
        db.flush()
    return gruppe


def standard_anlegen(db: Session) -> None:
    """Beim Start: Systemrolle/Admin-Gruppe sicherstellen; ohne jede Rolle zusätzlich "Mitarbeiter"."""
    ohne_rollen = db.query(func.count(Rolle.ID)).scalar() == 0
    admin_gruppe(db)
    gast_gruppe(db)
    if ohne_rollen:
        rolle = Rolle(Name="Mitarbeiter", Beschreibung="Tagesgeschäft", Angelegt_Am=datetime.now(),
                      rechte=[RolleRecht(Recht=r) for r in MITARBEITER_RECHTE])
        gruppe = Gruppe(Name="Mitarbeiter", Beschreibung="Tagesgeschäft", Angelegt_Am=datetime.now(), rollen=[rolle])
        db.add_all([rolle, gruppe])
    db.commit()


def zur_admin_gruppe(db: Session, benutzer: Benutzer) -> None:
    gruppe = admin_gruppe(db)
    if not any(m.Gruppe_ID == gruppe.ID for m in benutzer.mitgliedschaften):
        benutzer.mitgliedschaften.append(BenutzerGruppe(Gruppe_ID=gruppe.ID, Quelle="manuell"))


# --- Rollen -------------------------------------------------------------------------

def _rechte_pruefen(rechte: list[str]) -> list[str]:
    unbekannt = [r for r in rechte if r not in RECHTE]
    if unbekannt:
        raise ValueError(f"Unbekannte Rechte: {', '.join(unbekannt)}")
    return sorted(set(rechte))


def rolle_read(db: Session, rolle: Rolle) -> dict:
    gruppen = db.query(func.count(GruppeRolle.Gruppe_ID)).filter(GruppeRolle.Rolle_ID == rolle.ID).scalar()
    rechte = frozenset(r.Recht for r in rolle.rechte)
    return {
        "id": rolle.ID, "name": rolle.Name, "beschreibung": rolle.Beschreibung, "system": bool(rolle.System),
        "rechte": rechte_liste(rechte), "anzahl_gruppen": gruppen,
    }


def rollen(db: Session) -> list[Rolle]:
    return db.query(Rolle).order_by(Rolle.System.desc(), Rolle.Name).all()


def _rolle(db: Session, rolle_id: int) -> Rolle:
    rolle = db.get(Rolle, rolle_id)
    if rolle is None:
        raise LookupError("Rolle nicht gefunden")
    return rolle


def _name_frei(db: Session, modell, name: str, ausser_id: int | None = None) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Der Name fehlt.")
    abfrage = db.query(modell.ID).filter(modell.Name == name)
    if ausser_id is not None:
        abfrage = abfrage.filter(modell.ID != ausser_id)
    if abfrage.first():
        raise ValueError(f"Der Name „{name}“ ist schon vergeben.")
    return name


def rolle_anlegen(db: Session, name: str, beschreibung: str | None, rechte: list[str]) -> Rolle:
    rolle = Rolle(Name=_name_frei(db, Rolle, name), Beschreibung=(beschreibung or "").strip() or None,
                  Angelegt_Am=datetime.now(), rechte=[RolleRecht(Recht=r) for r in _rechte_pruefen(rechte)])
    db.add(rolle)
    db.flush()
    ereignisse.erfasse(db, "rolle_geaendert", text=f"{rolle.Name} angelegt")
    db.commit()
    return rolle


def rolle_aendern(db: Session, rolle_id: int, felder: dict) -> Rolle:
    rolle = _rolle(db, rolle_id)
    with notzugang_schuetzen(db):
        if rolle.System and ("rechte" in felder or "name" in felder):
            raise ValueError("Name und Rechte der Systemrolle können nicht geändert werden.")
        if felder.get("name"):
            rolle.Name = _name_frei(db, Rolle, felder["name"], rolle.ID)
        if "beschreibung" in felder:
            rolle.Beschreibung = (felder["beschreibung"] or "").strip() or None
        if felder.get("rechte") is not None:
            neue = _rechte_pruefen(felder["rechte"])
            in_gastgruppe = db.query(GruppeRolle.Gruppe_ID).join(Gruppe, Gruppe.ID == GruppeRolle.Gruppe_ID) \
                .filter(GruppeRolle.Rolle_ID == rolle.ID, Gruppe.Gast.is_(True)).first()
            if in_gastgruppe and GAST_VERBOTEN & set(neue):
                raise ValueError(GAST_VERBOTEN_TEXT)
            rolle.rechte = [RolleRecht(Recht=r) for r in neue]
        ereignisse.erfasse(db, "rolle_geaendert", text=rolle.Name)
    db.commit()
    gast_cache_leeren()
    return rolle


def rolle_loeschen(db: Session, rolle_id: int) -> None:
    rolle = _rolle(db, rolle_id)
    if rolle.System:
        raise ValueError("Die Systemrolle kann nicht gelöscht werden.")
    with notzugang_schuetzen(db):
        ereignisse.erfasse(db, "rolle_geaendert", text=f"{rolle.Name} gelöscht")
        db.delete(rolle)
    db.commit()
    gast_cache_leeren()


# --- Gruppen -------------------------------------------------------------------------

def gruppe_read(db: Session, gruppe: Gruppe) -> dict:
    mitglieder = db.query(func.count(BenutzerGruppe.Benutzer_ID)).filter(BenutzerGruppe.Gruppe_ID == gruppe.ID).scalar()
    return {
        "id": gruppe.ID, "name": gruppe.Name, "beschreibung": gruppe.Beschreibung, "oidc_gruppe": gruppe.Oidc_Gruppe,
        "rollen": [{"id": r.ID, "name": r.Name, "system": bool(r.System)} for r in sorted(gruppe.rollen, key=lambda r: r.Name)],
        "anzahl_mitglieder": mitglieder,
        "gast": bool(gruppe.Gast),
        "lesen": bool(gruppe.Lesen),
    }


def gruppen(db: Session) -> list[Gruppe]:
    # Die Gruppe "Ohne Anmeldung" zuerst
    return db.query(Gruppe).order_by(Gruppe.Gast.desc(), Gruppe.Name).all()


def _gruppe(db: Session, gruppe_id: int) -> Gruppe:
    gruppe = db.get(Gruppe, gruppe_id)
    if gruppe is None:
        raise LookupError("Gruppe nicht gefunden")
    return gruppe


def _oidc_gruppe(db: Session, wert: str | None, ausser_id: int | None = None) -> str | None:
    wert = (wert or "").strip() or None
    if wert is None:
        return None
    abfrage = db.query(Gruppe.Name).filter(func.lower(Gruppe.Oidc_Gruppe) == wert.lower())
    if ausser_id is not None:
        abfrage = abfrage.filter(Gruppe.ID != ausser_id)
    andere = abfrage.first()
    if andere:
        raise ValueError(f"Die OIDC-Gruppe „{wert}“ ist schon der Gruppe „{andere.Name}“ zugeordnet.")
    return wert


def _rollen_zu_ids(db: Session, rollen_ids: list[int]) -> list[Rolle]:
    gefunden = db.query(Rolle).filter(Rolle.ID.in_(rollen_ids)).all() if rollen_ids else []
    if len(gefunden) != len(set(rollen_ids)):
        raise ValueError("Unbekannte Rolle.")
    return gefunden


def gruppe_anlegen(db: Session, name: str, beschreibung: str | None, oidc_gruppe: str | None, rollen_ids: list[int]) -> Gruppe:
    gruppe = Gruppe(Name=_name_frei(db, Gruppe, name), Beschreibung=(beschreibung or "").strip() or None,
                    Oidc_Gruppe=_oidc_gruppe(db, oidc_gruppe), Angelegt_Am=datetime.now(),
                    rollen=_rollen_zu_ids(db, rollen_ids))
    db.add(gruppe)
    db.flush()
    ereignisse.erfasse(db, "gruppe_geaendert", text=f"{gruppe.Name} angelegt")
    db.commit()
    return gruppe


def gruppe_aendern(db: Session, gruppe_id: int, felder: dict) -> Gruppe:
    gruppe = _gruppe(db, gruppe_id)
    if gruppe.Gast:
        return _gast_gruppe_aendern(db, gruppe, felder)
    with notzugang_schuetzen(db):
        if felder.get("name"):
            gruppe.Name = _name_frei(db, Gruppe, felder["name"], gruppe.ID)
        if "beschreibung" in felder:
            gruppe.Beschreibung = (felder["beschreibung"] or "").strip() or None
        if "oidc_gruppe" in felder:
            neu = _oidc_gruppe(db, felder["oidc_gruppe"], gruppe.ID)
            if neu is None and gruppe.Oidc_Gruppe:
                # Ohne Zuordnung werden die über OIDC gekommenen Mitgliedschaften manuell
                db.query(BenutzerGruppe).filter(BenutzerGruppe.Gruppe_ID == gruppe.ID).update({"Quelle": "manuell"})
            gruppe.Oidc_Gruppe = neu
        if felder.get("rollen_ids") is not None:
            gruppe.rollen = _rollen_zu_ids(db, felder["rollen_ids"])
        ereignisse.erfasse(db, "gruppe_geaendert", text=gruppe.Name)
    db.commit()
    gast_cache_leeren()
    return gruppe


def _gast_gruppe_aendern(db: Session, gruppe: Gruppe, felder: dict) -> Gruppe:
    if felder.get("name") and felder["name"].strip() != gruppe.Name:
        raise ValueError("Der Name der Gruppe „Ohne Anmeldung“ kann nicht geändert werden.")
    if (felder.get("oidc_gruppe") or "").strip():
        raise ValueError("Die Gruppe „Ohne Anmeldung“ kann keiner OIDC-Gruppe zugeordnet werden.")
    if "beschreibung" in felder:
        gruppe.Beschreibung = (felder["beschreibung"] or "").strip() or None
    if felder.get("lesen") is not None:
        gruppe.Lesen = bool(felder["lesen"])
    if felder.get("rollen_ids") is not None:
        rollen = _rollen_zu_ids(db, felder["rollen_ids"])
        _gast_rollen_pruefen(rollen)
        gruppe.rollen = rollen
    ereignisse.erfasse(db, "gruppe_geaendert", text=f"{gruppe.Name}: "
                       + ", ".join([("alles ansehen" if gruppe.Lesen else "nichts ansehen")] + [r.Name for r in gruppe.rollen]))
    db.commit()
    gast_cache_leeren()
    return gruppe


def gruppe_loeschen(db: Session, gruppe_id: int) -> None:
    gruppe = _gruppe(db, gruppe_id)
    if gruppe.Gast:
        raise ValueError("Die Gruppe „Ohne Anmeldung“ kann nicht gelöscht werden.")
    with notzugang_schuetzen(db):
        ereignisse.erfasse(db, "gruppe_geaendert", text=f"{gruppe.Name} gelöscht")
        db.delete(gruppe)
    db.commit()


# --- Mitgliedschaften ------------------------------------------------------------------

def manuelle_gruppen_setzen(db: Session, benutzer: Benutzer, gruppen_ids: list[int]) -> bool:
    """Ersetzt die manuellen Mitgliedschaften; über OIDC gekommene bleiben. True bei Änderung (ohne Commit)."""
    gefunden = db.query(Gruppe.ID, Gruppe.Gast).filter(Gruppe.ID.in_(gruppen_ids)).all() if gruppen_ids else []
    if len(gefunden) != len(set(gruppen_ids)):
        raise ValueError("Unbekannte Gruppe.")
    if any(g.Gast for g in gefunden):
        raise ValueError("Die Gruppe „Ohne Anmeldung“ hat keine Mitglieder.")
    vorhanden = {g.ID for g in gefunden}
    oidc = {m.Gruppe_ID for m in benutzer.mitgliedschaften if m.Quelle == "oidc"}
    vorher = {m.Gruppe_ID for m in benutzer.mitgliedschaften if m.Quelle != "oidc"}
    ziel = vorhanden - oidc
    if ziel == vorher:
        return False
    benutzer.mitgliedschaften = [m for m in benutzer.mitgliedschaften if m.Quelle == "oidc" or m.Gruppe_ID in ziel]
    for gruppe_id in ziel - vorher:
        benutzer.mitgliedschaften.append(BenutzerGruppe(Gruppe_ID=gruppe_id, Quelle="manuell"))
    return True


def oidc_gruppen_abgleichen(db: Session, benutzer: Benutzer, token_gruppen: list[str]) -> int:
    """
    Gruppen mit OIDC-Zuordnung aus dem Token setzen bzw. entfernen (nur Quelle "oidc", manuelle bleiben).
    Gibt die Anzahl passender Gruppen zurück. Ohne Commit.
    """
    im_token = {str(g).strip().lower() for g in token_gruppen if str(g).strip()}
    zugeordnet = db.query(Gruppe).filter(Gruppe.Oidc_Gruppe.is_not(None)).all()
    passend = {g.ID for g in zugeordnet if g.Oidc_Gruppe.lower() in im_token}
    aktuell = {m.Gruppe_ID: m for m in benutzer.mitgliedschaften}

    for gruppe_id in passend:
        if gruppe_id not in aktuell:
            benutzer.mitgliedschaften.append(BenutzerGruppe(Gruppe_ID=gruppe_id, Quelle="oidc"))

    entfernen = [m for m in benutzer.mitgliedschaften if m.Quelle == "oidc" and m.Gruppe_ID not in passend]
    if entfernen:
        vorher = notzugang_vorhanden(db)
        behalten = [m for m in benutzer.mitgliedschaften if m not in entfernen]
        benutzer.mitgliedschaften = behalten
        db.flush()
        if vorher and not notzugang_vorhanden(db):
            # Der Anbieter würde den letzten Notzugang entfernen: Mitgliedschaften behalten
            logger.warning("OIDC-Abgleich für %s hätte den letzten Notzugang entfernt, Gruppen bleiben",
                           benutzer.Benutzername)
            for m in entfernen:
                benutzer.mitgliedschaften.append(BenutzerGruppe(Gruppe_ID=m.Gruppe_ID, Quelle="oidc"))
            db.flush()
    return len(passend)
