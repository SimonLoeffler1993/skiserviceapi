"""
Anmeldung mit OIDC (Authorization Code + PKCE), genau ein Anbieter, gewählt über OIDC_ANBIETER.

Ablauf:
1. GET /auth/oidc/start?ziel=…  →  302 zum Anbieter (state, nonce, PKCE im Speicher)
2. Anbieter  →  GET /auth/oidc/callback?code&state  →  Code tauschen, ID-Token prüfen, Benutzer finden
3. 302 auf ziel?code=<Einmalcode>  →  die App tauscht ihn über POST /auth/oidc/einloesen gegen Sitzungen

Das Client-Secret bleibt in der API. Erlaubte Rücksprungziele: ERLAUBTE_URSPRUENGE.
"""
import base64
import hashlib
import logging
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from sqlalchemy.orm import Session

from app.core import sicherheit
from app.models.benutzer import Benutzer
from app.services import einstellungen

logger = logging.getLogger(__name__)

CALLBACK_PFAD = "/api/v1/auth/oidc/callback"
_DISCOVERY_SEKUNDEN = 3600


@dataclass(frozen=True)
class AnbieterInfo:
    name: str
    issuer_noetig: bool
    # Claim, der den Benutzer dauerhaft kennzeichnet
    id_claim: str = "sub"
    fester_issuer: str | None = None
    # Kontoauswahl erzwingen: wichtig auf geteilten Geräten
    konto_waehlen: bool = False


ANBIETER: dict[str, AnbieterInfo] = {
    "authentik": AnbieterInfo("Authentik", issuer_noetig=True),
    # oid ist im ganzen Mandanten gleich, sub dagegen je App verschieden
    "microsoft": AnbieterInfo("Microsoft", issuer_noetig=False, id_claim="oid", konto_waehlen=True),
    "google": AnbieterInfo("Google", issuer_noetig=False, fester_issuer="https://accounts.google.com", konto_waehlen=True),
    "keycloak": AnbieterInfo("Keycloak", issuer_noetig=True),
    "generisch": AnbieterInfo("OIDC", issuer_noetig=True),
}

# Microsoft-Mandanten, hinter denen sich mehrere Verzeichnisse verbergen
_MS_SAMMEL_MANDANTEN = {"common", "organizations", "consumers"}


class OidcFehler(Exception):
    """code wird als ?fehler= an die App gegeben bzw. als Text angezeigt."""

    def __init__(self, code: str, text: str = ""):
        super().__init__(text or code)
        self.code = code
        self.text = text or code


# --- Konfiguration -----------------------------------------------------------

def anbieter_schluessel() -> str:
    schluessel = einstellungen.hole("OIDC_ANBIETER")
    return schluessel if schluessel in ANBIETER else "generisch"


def anbieter() -> AnbieterInfo:
    return ANBIETER[anbieter_schluessel()]


def button_text() -> str:
    return (einstellungen.hole("OIDC_BUTTON_TEXT") or "").strip() or f"Mit {anbieter().name} anmelden"


def _ms_mandant() -> str:
    return (einstellungen.hole("OIDC_MANDANT") or "").strip()


def konfigurierter_issuer() -> str:
    """Issuer aus den Einstellungen; kennzeichnet zugleich die Verknüpfung am Benutzer."""
    info = anbieter()
    if anbieter_schluessel() == "microsoft":
        mandant = _ms_mandant()
        if not mandant:
            raise OidcFehler("konfiguration", "Für Microsoft fehlt der Mandant (Tenant-ID).")
        return f"https://login.microsoftonline.com/{mandant}/v2.0"
    if info.fester_issuer:
        return info.fester_issuer
    issuer = (einstellungen.hole("OIDC_ISSUER") or "").strip()
    if not issuer:
        raise OidcFehler("konfiguration", "Der Issuer fehlt.")
    return issuer


def issuer_oder_none() -> str | None:
    try:
        return konfigurierter_issuer()
    except OidcFehler:
        return None


def redirect_uri() -> str:
    adresse = (einstellungen.hole("OIDC_API_ADRESSE") or "").strip().rstrip("/")
    if not adresse:
        raise OidcFehler("konfiguration", "Die öffentliche Adresse der API fehlt.")
    return adresse + CALLBACK_PFAD


def _konfiguration_pruefen() -> None:
    konfigurierter_issuer()
    redirect_uri()
    if not (einstellungen.hole("OIDC_CLIENT_ID") or "").strip():
        raise OidcFehler("konfiguration", "Die Client-ID fehlt.")
    if not einstellungen.hole("OIDC_CLIENT_SECRET"):
        raise OidcFehler("konfiguration", "Das Client-Secret fehlt.")
    if not einstellungen.urspruenge():
        raise OidcFehler("konfiguration", "Unter Benutzer & Anmeldung sind keine Adressen von Center, Kasse und Kundenterminal eingetragen.")


def aktiv() -> bool:
    """Eingeschaltet und vollständig eingerichtet."""
    if not einstellungen.hole("OIDC_AKTIV"):
        return False
    try:
        _konfiguration_pruefen()
    except OidcFehler:
        return False
    return True


# --- Discovery und Schlüssel ---------------------------------------------------

_discovery_cache: dict[str, tuple[float, dict]] = {}
_jwks_clients: dict[str, jwt.PyJWKClient] = {}
_cache_lock = threading.Lock()


def cache_leeren() -> None:
    with _cache_lock:
        _discovery_cache.clear()
        _jwks_clients.clear()


def discovery(issuer: str | None = None) -> dict:
    issuer = issuer or konfigurierter_issuer()
    jetzt = time.monotonic()
    with _cache_lock:
        eintrag = _discovery_cache.get(issuer)
        if eintrag and eintrag[0] > jetzt:
            return eintrag[1]
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        antwort = httpx.get(url, timeout=10, follow_redirects=True)
        antwort.raise_for_status()
        dokument = antwort.json()
    except Exception as e:
        raise OidcFehler("anbieter_nicht_erreichbar", f"Konfiguration von {url} nicht abrufbar: {e}")
    for feld in ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not dokument.get(feld):
            raise OidcFehler("anbieter_konfiguration", f"Die Konfiguration des Anbieters enthält kein „{feld}“.")
    with _cache_lock:
        _discovery_cache[issuer] = (jetzt + _DISCOVERY_SEKUNDEN, dokument)
    return dokument


def _jwks_client(url: str) -> jwt.PyJWKClient:
    with _cache_lock:
        client = _jwks_clients.get(url)
        if client is None:
            client = jwt.PyJWKClient(url, cache_keys=True, lifespan=_DISCOVERY_SEKUNDEN)
            _jwks_clients[url] = client
        return client


# --- Rücksprungziel --------------------------------------------------------------

def ziel_pruefen(ziel: str) -> str:
    """Nur Ziele auf einer Seite aus ERLAUBTE_URSPRUENGE (Schema + Host + Port)."""
    try:
        teile = urlsplit(ziel)
    except ValueError:
        raise OidcFehler("ziel_nicht_erlaubt")
    ursprung = f"{teile.scheme}://{teile.netloc}".lower()
    if teile.scheme not in ("http", "https") or not teile.netloc:
        raise OidcFehler("ziel_nicht_erlaubt")
    if ursprung not in [u.lower() for u in einstellungen.urspruenge()]:
        raise OidcFehler("ziel_nicht_erlaubt", f"{ursprung} steht nicht in den Adressen von Center, Kasse und Kundenterminal.")
    return ziel


def ziel_mit(ziel: str, werte: dict[str, str]) -> str:
    trenner = "&" if "?" in ziel else "?"
    return ziel + trenner + urlencode(werte)


# --- Ablauf ------------------------------------------------------------------------

def _b64url(daten: bytes) -> str:
    return base64.urlsafe_b64encode(daten).rstrip(b"=").decode("ascii")


def start_url(ziel: str, verknuepfen_benutzer_id: int | None = None) -> str:
    """URL zum Anbieter. Wirft OidcFehler, wenn OIDC aus oder unvollständig ist bzw. das Ziel nicht erlaubt."""
    if not einstellungen.hole("OIDC_AKTIV"):
        raise OidcFehler("oidc_aus", "Die Anmeldung mit OIDC ist ausgeschaltet.")
    _konfiguration_pruefen()
    ziel_pruefen(ziel)
    dokument = discovery()

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    sicherheit.oidc_states.ablegen(state, {
        "ziel": ziel,
        "nonce": nonce,
        "verifier": verifier,
        "issuer": konfigurierter_issuer(),
        "verknuepfen": verknuepfen_benutzer_id,
    })
    parameter = {
        "response_type": "code",
        "client_id": einstellungen.hole("OIDC_CLIENT_ID").strip(),
        "redirect_uri": redirect_uri(),
        "scope": (einstellungen.hole("OIDC_SCOPES") or "openid profile email").strip(),
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64url(hashlib.sha256(verifier.encode("ascii")).digest()),
        "code_challenge_method": "S256",
    }
    if anbieter().konto_waehlen:
        parameter["prompt"] = "select_account"
    trenner = "&" if "?" in dokument["authorization_endpoint"] else "?"
    return dokument["authorization_endpoint"] + trenner + urlencode(parameter)


def _code_tauschen(dokument: dict, code: str, verifier: str) -> dict:
    client_id = einstellungen.hole("OIDC_CLIENT_ID").strip()
    secret = einstellungen.hole("OIDC_CLIENT_SECRET")
    daten = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "code_verifier": verifier,
    }
    methoden = dokument.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
    auth = None
    if "client_secret_post" in methoden:
        daten.update(client_id=client_id, client_secret=secret)
    else:
        auth = (client_id, secret)
    try:
        antwort = httpx.post(dokument["token_endpoint"], data=daten, auth=auth, timeout=15,
                             headers={"Accept": "application/json"})
    except Exception as e:
        raise OidcFehler("anbieter_nicht_erreichbar", f"Token-Abruf fehlgeschlagen: {e}")
    if antwort.status_code != 200:
        logger.warning("OIDC Token-Abruf: %s %s", antwort.status_code, antwort.text[:500])
        raise OidcFehler("oidc", "Der Anbieter hat die Anmeldung abgelehnt.")
    return antwort.json()


def _id_token_pruefen(dokument: dict, id_token: str, nonce: str) -> dict:
    client_id = einstellungen.hole("OIDC_CLIENT_ID").strip()
    try:
        kopf = jwt.get_unverified_header(id_token)
        alg = kopf.get("alg", "")
        if alg.startswith("HS"):
            # Ohne Signaturschlüssel beim Anbieter (z.B. Authentik) wird mit dem Client-Secret signiert
            schluessel = einstellungen.hole("OIDC_CLIENT_SECRET")
        elif alg[:2] in ("RS", "PS", "ES"):
            schluessel = _jwks_client(dokument["jwks_uri"]).get_signing_key_from_jwt(id_token).key
        else:
            raise OidcFehler("oidc", f"Signaturverfahren {alg} wird nicht unterstützt.")
        claims = jwt.decode(
            id_token, schluessel, algorithms=[alg], audience=client_id, leeway=60,
            options={"verify_iss": False, "require": ["exp", "iat", "iss", "sub"]},
        )
    except OidcFehler:
        raise
    except Exception as e:
        logger.warning("OIDC ID-Token ungültig: %s", e)
        raise OidcFehler("oidc", "Das ID-Token des Anbieters ist ungültig.")

    erwartet = dokument["issuer"]
    if "{tenantid}" in erwartet:
        # Microsoft mit common/organizations: Issuer enthält den Mandanten des Kontos
        tid = claims.get("tid") or ""
        erwartet = erwartet.replace("{tenantid}", tid)
        erlaubt = [m.strip().lower() for m in (einstellungen.hole("OIDC_ERLAUBTE_MANDANTEN") or "").split(",") if m.strip()]
        if erlaubt and tid.lower() not in erlaubt:
            raise OidcFehler("mandant_nicht_erlaubt", "Konten dieses Mandanten sind nicht zugelassen.")
    if claims.get("iss") != erwartet:
        raise OidcFehler("oidc", "Das ID-Token stammt nicht vom eingestellten Anbieter.")
    if claims.get("nonce") != nonce:
        raise OidcFehler("oidc", "Das ID-Token passt nicht zu dieser Anmeldung.")
    return claims


def _benutzername_vorschlag(db: Session, claims: dict) -> str:
    roh = claims.get("preferred_username") or claims.get("email") or claims.get("name") or "oidc"
    name = re.sub(r"[^A-Za-z0-9._@-]", "", str(roh).replace(" ", "."))[:45] or "oidc"
    if len(name) < 2:
        name = "oidc"
    kandidat, nummer = name, 2
    while db.query(Benutzer.ID).filter(Benutzer.Benutzername == kandidat).first():
        kandidat = f"{name}{nummer}"
        nummer += 1
    return kandidat


@dataclass
class Identitaet:
    issuer: str
    mandant: str
    kennung: str
    email: str | None
    name: str | None
    claims: dict


def _identitaet(issuer: str, claims: dict) -> Identitaet:
    info = anbieter()
    kennung = claims.get(info.id_claim) or claims["sub"]
    mandant = (claims.get("tid") or "") if anbieter_schluessel() == "microsoft" else ""
    return Identitaet(issuer=issuer, mandant=mandant, kennung=str(kennung),
                      email=claims.get("email") or (claims.get("preferred_username") if "@" in str(claims.get("preferred_username", "")) else None),
                      name=claims.get("name"), claims=claims)


def benutzer_zur_identitaet(db: Session, identitaet: Identitaet) -> Benutzer | None:
    return (db.query(Benutzer)
            .filter(Benutzer.Oidc_Issuer == identitaet.issuer,
                    Benutzer.Oidc_Mandant == identitaet.mandant,
                    Benutzer.Oidc_Kennung == identitaet.kennung)
            .one_or_none())


def verknuepfen(benutzer: Benutzer, identitaet: Identitaet) -> None:
    benutzer.Oidc_Issuer = identitaet.issuer
    benutzer.Oidc_Mandant = identitaet.mandant
    benutzer.Oidc_Kennung = identitaet.kennung
    if not benutzer.Email and identitaet.email:
        benutzer.Email = identitaet.email[:255]


def callback(db: Session, code: str | None, state: str | None, fehler: str | None) -> str:
    """
    Verarbeitet die Rückkehr vom Anbieter und gibt die URL zurück, auf die weitergeleitet wird.
    Wirft OidcFehler nur, wenn der State unbekannt ist (dann gibt es kein Ziel).
    """
    eintrag = sicherheit.oidc_states.entnehmen(state or "")
    if eintrag is None:
        raise OidcFehler("state_ungueltig", "Die Anmeldung ist abgelaufen. Bitte erneut starten.")
    ziel = eintrag["ziel"]
    if fehler:
        return ziel_mit(ziel, {"fehler": "abgebrochen" if fehler == "access_denied" else "oidc"})
    if not code:
        return ziel_mit(ziel, {"fehler": "oidc"})
    try:
        if eintrag["issuer"] != konfigurierter_issuer():
            raise OidcFehler("oidc", "Der Anbieter wurde während der Anmeldung geändert.")
        dokument = discovery()
        tokens = _code_tauschen(dokument, code, eintrag["verifier"])
        if not tokens.get("id_token"):
            raise OidcFehler("oidc", "Der Anbieter hat kein ID-Token geliefert.")
        claims = _id_token_pruefen(dokument, tokens["id_token"], eintrag["nonce"])
        identitaet = _identitaet(eintrag["issuer"], claims)

        if eintrag.get("verknuepfen"):
            return ziel_mit(ziel, _verknuepfen_abschliessen(db, eintrag["verknuepfen"], identitaet))

        benutzer = benutzer_zur_identitaet(db, identitaet)
        if benutzer is None:
            benutzer = _neuer_benutzer(db, identitaet)
        if benutzer.Freigabe_Ausstehend:
            return ziel_mit(ziel, {"fehler": "freigabe_ausstehend"})
        if not benutzer.Aktiv:
            return ziel_mit(ziel, {"fehler": "gesperrt"})
        einmalcode = secrets.token_urlsafe(32)
        sicherheit.oidc_einmalcodes.ablegen(einmalcode, {"benutzer_id": benutzer.ID})
        return ziel_mit(ziel, {"code": einmalcode})
    except OidcFehler as e:
        logger.warning("OIDC-Anmeldung fehlgeschlagen: %s", e.text)
        return ziel_mit(ziel, {"fehler": e.code})


def _neuer_benutzer(db: Session, identitaet: Identitaet) -> Benutzer:
    from app.services import ereignisse

    freigeben = bool(einstellungen.hole("OIDC_AUTO_FREIGABE"))
    benutzer = Benutzer(
        Benutzername=_benutzername_vorschlag(db, identitaet.claims),
        Anzeigename=(identitaet.name or identitaet.email or identitaet.kennung)[:100],
        Email=identitaet.email[:255] if identitaet.email else None,
        Rolle="mitarbeiter",
        Aktiv=freigeben,
        Freigabe_Ausstehend=not freigeben,
        Angelegt_Am=datetime.now(),
    )
    verknuepfen(benutzer, identitaet)
    db.add(benutzer)
    db.flush()
    ereignisse.erfasse(db, "benutzer_angelegt", benutzer_id=benutzer.ID, benutzer_name=benutzer.Anzeigename,
                       text=f"Über {anbieter().name}" + ("" if freigeben else ", Freigabe ausstehend"))
    db.commit()
    return benutzer


def _verknuepfen_abschliessen(db: Session, benutzer_id: int, identitaet: Identitaet) -> dict[str, str]:
    benutzer = db.get(Benutzer, benutzer_id)
    if benutzer is None:
        return {"fehler": "oidc"}
    vorhanden = benutzer_zur_identitaet(db, identitaet)
    if vorhanden is not None and vorhanden.ID != benutzer.ID:
        if vorhanden.Freigabe_Ausstehend and not vorhanden.Passwort_Hash:
            # Früher schon einmal über OIDC angemeldet und nie freigegeben: dieser Eintrag geht im Konto auf
            db.delete(vorhanden)
            db.flush()
        else:
            return {"fehler": "bereits_verknuepft"}
    verknuepfen(benutzer, identitaet)
    db.commit()
    return {"verknuepft": "1"}


def testen() -> dict:
    """Für „Verbindung testen“ im Center."""
    _konfiguration_pruefen()
    cache_leeren()
    dokument = discovery()
    return {
        "anbieter": anbieter().name,
        "issuer": dokument["issuer"],
        "authorization_endpoint": dokument["authorization_endpoint"],
        "redirect_uri": redirect_uri(),
    }
