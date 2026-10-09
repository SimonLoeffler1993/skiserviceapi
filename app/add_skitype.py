# app/db/seed_skiart.py
import logging

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.materialski import SkiArt  # Import-Pfad anpassen

logger = logging.getLogger(__name__)

SKIARTEN = [
    "Allmountain",
    "Sport Carver",
    "Piste",
    "Kinder",
    "Jugend",
    "Freeride",
    "Tour",
]


def seed_skiarten(db: Session) -> None:
    if db.execute(select(SkiArt.ID).limit(1)).first() is not None:
        logger.info("Tabelle skiart nicht leer, Seed übersprungen")
        return

    db.execute(insert(SkiArt), [{"Art": art} for art in SKIARTEN])
    db.commit()
    logger.info("%d Skiarten eingespielt", len(SKIARTEN))


def seed_if_empty() -> None:
    with SessionLocal() as db:
        seed_skiarten(db)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    seed_if_empty()