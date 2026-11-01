import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.deps import get_db

router = APIRouter(
    prefix="/health",
    tags=["health"],
)

logger = logging.getLogger(__name__)


@router.get("")
def health(db: Session = Depends(get_db)):
    """
    Healthcheck für Skiscanner und Monitoring: API läuft und die Datenbank antwortet.
    Bei nicht erreichbarer Datenbank 503.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Healthcheck: Datenbank nicht erreichbar")
        return JSONResponse(status_code=503, content={"status": "fehler", "datenbank": False})
    return {"status": "ok", "datenbank": True}
