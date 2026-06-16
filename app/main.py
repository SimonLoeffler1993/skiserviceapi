from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.api.v1 import kunden, orte, event, saisonverleih, ettiket, saison, quittungen
from app.api.v1.material import ski, schuh, stock
from app.api.v1.scanner import skiscanner
from app.api.v1 import skiservice

# TODO: #10 Logging einstellungen
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
    datefmt="%d.%m.%Y %H:%M:%S",
)

app = FastAPI(title="SkiApp API", version="0.0.1")
logger = logging.getLogger(__name__)

# TODO: Alembic in den Startprozess integrieren
# Dadurch werden bei jedem Start die neuesten DB Migrationen ausgeführt.

# TODO: #9 CORS in einstellungen
# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development; adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

appPrefix = "/api/v1"

app.include_router(kunden.router, prefix=appPrefix)
app.include_router(orte.router, prefix=appPrefix)
app.include_router(event.router, prefix=appPrefix)
app.include_router(saisonverleih.router, prefix=appPrefix)
app.include_router(ski.router, prefix=appPrefix)
app.include_router(schuh.router, prefix=appPrefix)
app.include_router(stock.router, prefix=appPrefix)
app.include_router(ettiket.router, prefix=appPrefix)
app.include_router(saison.router, prefix=appPrefix)
app.include_router(quittungen.router, prefix=appPrefix)
app.include_router(skiscanner.router, prefix=appPrefix)
app.include_router(skiservice.router, prefix=appPrefix)

@app.get("/")
def read_root():
    return {"Hello": "World"}





