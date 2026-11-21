from fastapi import FastAPI, HTTPException
from fastapi import Depends
import logging
from contextlib import asynccontextmanager

from app.api.v1 import kunden, orte, event, saisonverleih, ettiket, saison, quittungen
from app.api.v1.material import ski, schuh, stock
from app.api.v1.scanner import skiscanner
from app.api.v1 import skiservice
from app.api.v1 import kasse
from app.api.v1 import einstellungen
from app.api.v1 import bindungsdaten
from app.api.v1 import handware
from app.api.v1 import health
from app.api.v1 import checkin
from app.api.v1 import mailvorlagen
from app.api.v1 import mailprotokoll
from app.api.v1 import werkstatt
from app.api.v1 import auth, benutzer, geraete, ereignisse, rollen, gruppen
from app.core.cors import EinstellungsCors
from app.core.zugriff import angemeldet, recht, schreibrecht
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services import checkin_schluessel
from app.services import einstellungen as einstellungen_service
from app.services import mailvorlagen as mailvorlagen_service
from app.services import anmeldung as anmeldung_service
from app.services import nachvollziehbarkeit

# angelegt_von / geaendert_von bei jedem Flush setzen
nachvollziehbarkeit.registrieren()

# TODO: #10 Logging einstellungen
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
    datefmt="%d.%m.%Y %H:%M:%S",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Base.metadata.create_all(bind=engine)
    try:
        # Alte Umgebungsvariablen einmalig in die Einstellungen übernehmen
        einstellungen_service.aus_umgebung_uebernehmen()
    except Exception:
        logging.getLogger(__name__).exception("Einstellungen konnten nicht aus der Umgebung übernommen werden")
    try:
        # Public Key für die Check-in-App bereitstellen, siehe CHECKIN_PUBLIC_KEY_ORDNER
        with SessionLocal() as db:
            checkin_schluessel.beim_start(db)
    except Exception:
        logging.getLogger(__name__).exception("Check-in-Schlüssel konnte nicht bereitgestellt werden")
    try:
        # Fehlende Mail-Vorlagen mit dem Originaltext anlegen
        with SessionLocal() as db:
            mailvorlagen_service.beim_start(db)
    except Exception:
        logging.getLogger(__name__).exception("Mail-Vorlagen konnten nicht angelegt werden")
    try:
        # Abgelaufene Sitzungen aufräumen, ggf. ersten Admin aus ADMIN_BENUTZER / ADMIN_PASSWORT anlegen
        with SessionLocal() as db:
            anmeldung_service.beim_start(db)
    except Exception:
        logging.getLogger(__name__).exception("Benutzerverwaltung konnte nicht vorbereitet werden")
    yield

app = FastAPI(title="SkiApp API", version="0.0.1", lifespan=lifespan)
logger = logging.getLogger(__name__)


# CORS nach ERLAUBTE_URSPRUENGE (Einstellungen → Benutzer & Anmeldung)
app.add_middleware(EinstellungsCors)

appPrefix = "/api/v1"

# Rechte, siehe app/core/rechte.py und app/core/zugriff.py. Lesen darf jeder Angemeldete, Schreiben braucht
# das Recht des Routers. Ohne Vorgabe hier (kunden, orte, event, saison, skiscanner, health, auth, benutzer,
# rollen, gruppen, geraete, ereignisse) steht der Schutz an den einzelnen Routen bzw. im Router selbst.
ANGEMELDET = [Depends(angemeldet)]


def schreiben(name: str, ausser: tuple[str, ...] = ()) -> list:
    return [Depends(schreibrecht(name, ausser))]


def ganz(name: str) -> list:
    return [Depends(recht(name))]

app.include_router(kunden.router, prefix=appPrefix)
app.include_router(orte.router, prefix=appPrefix)
app.include_router(event.router, prefix=appPrefix)
app.include_router(saisonverleih.router, prefix=appPrefix, dependencies=schreiben("verleih.bearbeiten", ausser=("/preise",)))
app.include_router(ski.router, prefix=appPrefix, dependencies=schreiben("material.bearbeiten"))
app.include_router(schuh.router, prefix=appPrefix, dependencies=schreiben("material.bearbeiten"))
app.include_router(stock.router, prefix=appPrefix, dependencies=schreiben("material.bearbeiten"))
app.include_router(ettiket.router, prefix=appPrefix, dependencies=ANGEMELDET)
app.include_router(saison.router, prefix=appPrefix)
app.include_router(quittungen.router, prefix=appPrefix, dependencies=ANGEMELDET)
app.include_router(skiscanner.router, prefix=appPrefix)
app.include_router(skiservice.router, prefix=appPrefix, dependencies=schreiben("skiservice.bearbeiten", ausser=("/preise", "/bindungsservice")))
app.include_router(kasse.router, prefix=appPrefix, dependencies=schreiben("kasse.kassieren"))
app.include_router(einstellungen.router, prefix=appPrefix, dependencies=ganz("einstellungen.verwalten"))
app.include_router(bindungsdaten.router, prefix=appPrefix, dependencies=schreiben("skiservice.bearbeiten"))
app.include_router(handware.router, prefix=appPrefix, dependencies=schreiben("preise.verwalten"))
app.include_router(health.router, prefix=appPrefix)
app.include_router(checkin.router, prefix=appPrefix, dependencies=ANGEMELDET)
app.include_router(mailvorlagen.router, prefix=appPrefix, dependencies=ganz("vorlagen.verwalten"))
app.include_router(mailprotokoll.router, prefix=appPrefix, dependencies=ANGEMELDET)
app.include_router(werkstatt.router, prefix=appPrefix, dependencies=ANGEMELDET)
app.include_router(auth.router, prefix=appPrefix)
app.include_router(benutzer.router, prefix=appPrefix)
app.include_router(rollen.router, prefix=appPrefix)
app.include_router(gruppen.router, prefix=appPrefix)
app.include_router(geraete.router, prefix=appPrefix)
app.include_router(ereignisse.router, prefix=appPrefix)

@app.get("/")
def read_root():
    return {"Hello": "World"}





