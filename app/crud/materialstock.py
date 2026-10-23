from sqlalchemy.orm import Session

from app.crud import materialverwendung as verwendung
from app.crud.materialverwendung import MaterialUngueltig
from app.models.materialstock import Skistock
from app.models.saisonverleih import SaisonVerleihMaterial


def _benutzte_stoecke(db: Session) -> set:
    return {nr for (nr,) in db.query(SaisonVerleihMaterial.stockbez_ID).filter(SaisonVerleihMaterial.stockbez_ID.isnot(None)).distinct()}


def get_alle_skistocke(db: Session, mit_ausgemustert: bool = True):
    query = db.query(Skistock)
    if not mit_ausgemustert:
        query = query.filter(Skistock.Ausgemustert == False)  # noqa: E712
    stoecke = query.order_by(Skistock.Bezeichnung).all()
    return verwendung.setze_im_verleih(stoecke, _benutzte_stoecke(db), lambda stock: stock.ID)


def get_skistock(db: Session, stock_id: int):
    return db.get(Skistock, stock_id)


def create_skistock(db: Session, bezeichnung: str):
    db_skistock = Skistock(Bezeichnung=bezeichnung)
    db.add(db_skistock)
    db.commit()
    db.refresh(db_skistock)
    return db_skistock


def aendere_skistock(db: Session, stock_id: int, bezeichnung: str):
    stock = db.get(Skistock, stock_id)
    if stock is None:
        return None
    if not bezeichnung.strip():
        raise MaterialUngueltig("Die Bezeichnung darf nicht leer sein.")
    stock.Bezeichnung = bezeichnung.strip()
    db.commit()
    db.refresh(stock)
    stock.ImVerleih = stock.ID in _benutzte_stoecke(db)
    return stock


def verwendung_skistock(db: Session, stock: Skistock) -> list[dict]:
    return verwendung.verwendung(db, SaisonVerleihMaterial.stockbez_ID == stock.ID)


def loesche_skistock(db: Session, stock: Skistock):
    verwendung.loesche(db, stock, SaisonVerleihMaterial.stockbez_ID == stock.ID, f"Stock {stock.Bezeichnung}")
