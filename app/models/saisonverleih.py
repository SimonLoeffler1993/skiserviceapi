from sqlalchemy import Column, Integer, String, Double, Date, ForeignKey, Boolean
from app.db.base import Base
from sqlalchemy.orm import relationship

# Wird Importiert um Fehler zu vermeiden
# auch wen diese nicht direkt verwendet werden
from app.models.saison import Saison
from app.models.kunde import SkiKunde
from app.models.materialski import EigenSki
from app.models.materialschuh import EigenSchuh
from app.models.materialstock import Skistock

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



class SaisonVerleih(Base):
    __tablename__ = "saisonverleih"
    ID = Column(Integer, primary_key=True)
    Kunde_ID = Column(Integer, ForeignKey("adresse.ID"))
    Kunde = relationship("SkiKunde", backref="saisonverleih")
    Ueberweisung = Column(Integer)
    Bezahlt = Column(Boolean)
    Bezahlt_Am = Column(Date, nullable=True)
    Zurueck = Column(Integer, nullable=True)
    Zurueck_Am = Column(Date, nullable=True)
    Bemerkung = Column(String, nullable=True)
    Saison_ID = Column(Integer,ForeignKey("saisons.ID"))
    Saison = relationship("Saison", backref="saisonverleih")
    Abgerechnet = Column(Integer, nullable=True)
    Name = Column(String)
    Start_Am = Column(Date)
    QuittungID = Column(Integer, nullable=True)
    Material = relationship("SaisonVerleihMaterial", backref="saisonverleihmaterial")

class SaisonVerleihMaterial(Base):
    __tablename__ = "saisonverleihmaterial"
    ID = Column(Integer, primary_key=True)
    SaisonVerlei_ID = Column(Integer, ForeignKey("saisonverleih.ID"))
    skinr = Column(String, ForeignKey("eigenski.SkiNr"), nullable=True)
    Ski = relationship("EigenSki", primaryjoin="SaisonVerleihMaterial.skinr == EigenSki.SkiNr", backref="saisonverleihmaterial", foreign_keys=[skinr])  # wichtig, sonst meckert SQLAlchemy bei Mehrdeutigkeiten)
    schuhnr = Column(Integer, ForeignKey("eigenschuh.ID"), nullable=True)
    Schuh = relationship("EigenSchuh", backref="saisonverleihmaterial")
    stockbez_ID = Column(Integer, ForeignKey("verleihstocke.ID"), nullable=True)
    Stock = relationship("Skistock", backref="saisonverleihmaterial")
    stocklaenge = Column(Integer, nullable=True)
    Preis = Column(Double)
    SkiFahrerName = Column(String(150), nullable=True, default=None)