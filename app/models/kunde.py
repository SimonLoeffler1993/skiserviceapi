from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base

# Wird Importiert um Fehler zu vermeiden
# auch wen diese nicht direkt verwendet werden
from app.models.ort import Ort

class SkiKunde(Base):
    __tablename__ = "adresse"
    ID = Column(Integer, primary_key=True)
    Nachname = Column(String(20))
    Vorname = Column(String(20))
    Anrede = Column(String(1), default="f")
    Strasse= Column(String(250))
    Plz = Column(Integer(), ForeignKey('postleitzahl.Postlz'))
    Ort = relationship("Ort", backref="adresse")
    Tel = Column(String(50))
    Email = Column(String(50))
    Tel1 = Column(String(50))
    Tel2 = Column(String(50))
    Email1 = Column(String(50))
    Email2 = Column(String(50))
    AusweisNr = Column(String(15), default="0")
    BDay = Column(String(15))