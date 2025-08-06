from sqlalchemy import Column, Integer, String, Double
from app.db.base import Base

class SkiSaisonverleihPreise(Base):
    __tablename__ = "saisonverleihpreise"
    ID = Column(Integer, primary_key=True)
    Bezeichnung = Column(String(50), nullable=False)
    Preis = Column(Double, nullable=False)
    vonL = Column(Integer, nullable=True)
    bisL = Column(Integer, nullable=True)
    SkiArt_ID = Column(Integer, nullable=True)
    inaktiv = Column(Integer, default=0)
    # TODO Lexoffice ID für Synchronisation

    