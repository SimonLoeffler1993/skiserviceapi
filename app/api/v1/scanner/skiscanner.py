from fastapi import APIRouter, Depends, HTTPException, Request
from urllib.parse import urlparse, parse_qs

from app.schemas.scanner import ScannerRead, TriggerStatus

router = APIRouter(
    prefix="/scanner/skiscanner",
    tags=["Scanner"],
    responses={404: {"description": "Not found"}},
)

def codeURL2SaisonID(codeURL: str):
    parsed_url = urlparse(codeURL)
    saison_id = parsed_url.path.strip("/").split("/")[-1] or None
    ski_nr = parse_qs(parsed_url.query).get("ski", [None])[0] 

    return saison_id, ski_nr
    

@router.get("/test")
async def test():
    return {"message": "Skiscanner API is working!"}

@router.post("/scan")
async def scan(scanner_data: ScannerRead):
    """
    Wertet die gesendeten Daten vom Skiscanner aus.
    """
    
    if scanner_data.trigger == TriggerStatus.fertig:
        saisonID, ski_nr = codeURL2SaisonID(scanner_data.code)
        print(f"Scan abgeschlossen. SaisonID: {saisonID}, Ski-Nr: {ski_nr}")

    return {"message": "Scanning in progress..."}