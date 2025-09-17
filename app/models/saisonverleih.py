from sqlalchemy import Column, Integer, String, Double, Date, ForeignKey
from app.db.base import Base
from sqlalchemy.orm import relationship

from app.models.kunde import SkiKunde
from app.models.saison import Saison

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

class SaisonVerleihMaterial(Base):
    __tablename__ = "saisonverleihmaterial"
    ID = Column(Integer, primary_key=True)
    SaisonVerlei_ID = Column(Integer, ForeignKey("saisonverleih.ID"))
    skinr = Column(String, ForeignKey('eigenski.SkiNr'))
    Ski = relationship("EigenSki",backref="saisonverleihmaterial")
    schuhnr = Column(Integer, ForeignKey('eigenschuh.ID'))
    Schuh = relationship("EigenSchuh", backref="saisonverleihmaterial")
    stockbez_ID = Column(Integer, ForeignKey("verleihstocke.ID"))
    Stock = relationship("Skistock", backref="saisonverleihmaterial")
    stocklaenge = Column(Integer)
    Preis = Column(Double)

class SaisonVerleih(Base):
    __tablename__ = "saisonverleih"
    ID = Column(Integer, primary_key=True)
    Kunde_ID = Column(Integer, ForeignKey(SkiKunde.ID))
    Kunde = relationship(SkiKunde)
    Ueberweisung = Column(Integer)
    Bezahlt = Column(Integer)
    Bezahlt_Am = Column(Date)
    Zurueck = Column(Integer)
    Zurueck_Am = Column(Date)
    Bemerkung = Column(String)
    Saison_ID = Column(Integer,ForeignKey(Saison.ID))
    Saison = relationship(Saison, backref="saisonverleih")
    Abgerechnet = Column(Integer)
    Name = Column(String)
    Start_Am = Column(Date)
    QuittungID = Column(Integer)
    # Material = relationship("SaisonVerleihMaterial", backref="saisonverleihmaterial")