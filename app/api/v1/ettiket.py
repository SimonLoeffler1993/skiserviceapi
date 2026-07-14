from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.crud import saisonverleih as crud_saisonverleih
from app.crud import materialschuh as crud_materialschuh
from app.crud import skiservice as crud_skiservice
from app.utils.skiEttiket import SkiEttiket

from app.services.skiserviceauftrag import skiServiceEttiketDrucken, skiServiceEttiketEinzelnDrucken

from app.schemas.ettiketenprint import EttiketPrintRequest, EttiketPrintSkisSchema
from app.schemas.skiservice import AuftragSchema

router = APIRouter(
    prefix="/ettiket",
    tags=["Ettiketen"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test")
async def test():
    return {"message": "Ettiket API is working!"}

@router.get("/saisonfahrer/{saisonverleih_id}" , response_model=EttiketPrintRequest)
def print_saisonfahrer_ettiket(saisonverleih_id: int, db: Session = Depends(get_db)):
    """
    Druckt Ettiket für alle Fahrer im Saisonverleih^
    - Nur wenn FahrerName vorhanden ist
    - Pro Material 2x Drucken
    - Skier, Schuhe, Stöcke
    """
    labelPrint = False

    saisonverleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    if not saisonverleih:
        raise HTTPException(status_code=404, detail="Saisonverleih not found")
    
    try:
        ettiket_printer = SkiEttiket()
        
        for material in saisonverleih.Material:
            print(material.SkiFahrerName)
            if material.SkiFahrerName != None:
                # Ski Drucken
                if material.skinr or material.skinr != "":
                    labelPrint = True
                    ettiket_printer.saisonFahererName(str(material.SkiFahrerName))
                    ettiket_printer.saisonFahererName(str(material.SkiFahrerName))
                # Schuh Drucken
                if material.schuhnr or material.schuhnr != "":
                    labelPrint = True
                    ettiket_printer.saisonFahererName(str(material.SkiFahrerName))
                    ettiket_printer.saisonFahererName(str(material.SkiFahrerName))
                # Stock Drucken
                if material.stockbez_ID or material.stockbez_ID != -1:
                    labelPrint = True
                    ettiket_printer.saisonFahererName(str(material.SkiFahrerName))
                    ettiket_printer.saisonFahererName(str(material.SkiFahrerName))
        if labelPrint:
            # print("Drucke Ettiketen...")
            ettiket_printer.drucken()
    except Exception as e:
        return {"success": False, "message": f"Error printing ettiket: {str(e)}"}

    if not labelPrint:
        return {"success": False, "message": "Kein Fahrername für Ettiket vorhanden."}
    return {"success": True, "message": f"Ettiket for Saisonverleih ID {saisonverleih_id} printed."}

@router.post("/schuh/{schuhID}" , response_model=EttiketPrintRequest)
def print_schuh_ettiket(schuhID: str, db: Session = Depends(get_db)):
    """
    Druckt Ettiket für Schuh
    """
    schuh = crud_materialschuh.get_eigen_schuhe(db, schuhID)
    if not schuh:
        return {"success": False, "message": f"Error Drucken ettiket: Schuh {schuhID} nicht gefunden."}
    try:
        ettiket_printer = SkiEttiket()
        ettiket_printer.SchuhEttiket(hersteller=schuh.Modell.Hersteller.Name, modell=schuh.Modell.Modell, groesse=str(schuh.Groese), qrdata=schuhID)
        ettiket_printer.drucken()
    except Exception as e:
        return {"success": False, "message": f"Error printing ettiket: {str(e)}"}

    return {"success": True, "message": f"Ettiket for Schuh {schuhID} printed."}

@router.post("/serviceauftrag/{auftragid}", response_model=EttiketPrintRequest)
def print_serviceAuftrag_erriket(auftragid: int, db: Session = Depends(get_db)):
    """
    Druck alle Ettiketen für einen Skiserice
    """
    try:
        auftrag = crud_skiservice.getSkiserviceAuftrag(db, auftragid)

        # Sql Alchemy Modell in object
        skiserviceAuftrag = AuftragSchema.model_validate(auftrag)

        skiServiceEttiketDrucken(skiserviceAuftrag)
    except Exception as e:
        return {"success": False, "message": f"Fehler beim Drucken ettiket: {str(e)}"}

    if not auftrag:
        return {"success": False, "message": f"Error Drucken ettiket: Skiservice {auftragid} nicht gefunden."}
    
    return {"success": True, "message": f"Ettiket für Skiservice {auftragid} ausgedruckt!"}

@router.post("/serviceskis", response_model=EttiketPrintRequest)
def print_serviceSki_ettiket(ettiket_data: EttiketPrintSkisSchema, db: Session = Depends(get_db)):
    """
    Druck Ettiketen für spezifische Skis eines Skiservice-Auftrags
    Die auftrag id ist optional, allerdings müssen alle Ski aus dem selben Auftrag stammen
    """
    try:
        if ettiket_data.auftrag_id is None:
            # Wenn keine auftrag_id übergeben wurde, dann die auftrag_id anhand der ski_ids ermitteln
            if len(ettiket_data.ski_ids) == 0:
                return {"success": False, "message": "Keine Ski IDs übergeben."}
            
            auftrag_id = crud_skiservice.get_auftragid_from_skiid(db, ettiket_data.ski_ids[0])
            if auftrag_id is None:
                return {"success": False, "message": f"Error Drucken ettiket: Auftrag für Ski ID {ettiket_data.ski_ids[0]} nicht gefunden."}
            ettiket_data.auftrag_id = auftrag_id
            
        auftrag = crud_skiservice.getSkiserviceAuftrag(db, ettiket_data.auftrag_id)

        # Sql Alchemy Modell in object
        skiserviceAuftrag = AuftragSchema.model_validate(auftrag)

        skiServiceEttiketEinzelnDrucken(skiserviceAuftrag, ettiket_data.ski_ids)
    except Exception as e:
        return {"success": False, "message": f"Fehler beim Drucken ettiket: {str(e)}"}

    if not auftrag:
        return {"success": False, "message": f"Error Drucken ettiket: Skiservice {ettiket_data.auftrag_id} nicht gefunden."}

    return {"success": True, "message": f"Ettiket für Skiservice {ettiket_data.auftrag_id} ausgedruckt!"}
