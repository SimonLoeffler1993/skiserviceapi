# app/db/seed.py
import csv
import logging
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal 
from app.models.ort import Ort  # Import-Pfad anpassen

logger = logging.getLogger(__name__)

PLZ_FILE = Path(__file__).parent / "deutscheplz.csv"  # Dateiname anpassen, falls er anders heißt
CHUNK_SIZE = 5000


def load_plz_rows() -> list[dict]:
    rows: dict[int, str] = {}
    # utf-8-sig entfernt ein evtl. BOM (z. B. bei Excel-Exporten)
    with PLZ_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for line in reader:
            plz_raw = (line.get("Plz") or "").strip()
            if not plz_raw:
                continue  # Leerzeilen überspringen
            plz = int(plz_raw)
            ort = (line.get("Ort") or "").strip()[:30]  # Spalte ist String(30)
            rows.setdefault(plz, ort)  # PLZ ist Primary Key: erster Eintrag gewinnt
    return [{"Postlz": plz, "Ort": ort} for plz, ort in rows.items()]


def seed_plz(db: Session) -> None:
    if db.execute(select(Ort.Postlz).limit(1)).first() is not None:
        logger.info("Tabelle postleitzahl nicht leer, Seed übersprungen")
        return

    if not PLZ_FILE.exists():
        raise FileNotFoundError(f"PLZ-Datei {PLZ_FILE} nicht gefunden")

    rows = load_plz_rows()
    for i in range(0, len(rows), CHUNK_SIZE):
        db.execute(insert(Ort), rows[i : i + CHUNK_SIZE])
    db.commit()
    logger.info("%d Postleitzahlen eingespielt", len(rows))


def seed_if_empty() -> None:
    with SessionLocal() as db:
        seed_plz(db)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    seed_if_empty()