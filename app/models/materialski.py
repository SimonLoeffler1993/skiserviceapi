from sqlalchemy import Column, Integer, String, ForeignKey, Double
from sqlalchemy.orm import relationship

from app.db.base import Base

class VerleihSkiHersteller(Base):
    __tablename__ = "verleihskihersteller"
    ID = Column(Integer, primary_key=True)
    Name = Column(String)

class SkiArt(Base):
    __tablename__ = "skiart"
    ID = Column(Integer, primary_key=True)
    Art = Column(String)

class VerleihSkiModell(Base):
    __tablename__ = "verleihskimodell"
    ID = Column(Integer, primary_key=True)
    Modell = Column(String)
    Art_ID = Column(Integer, ForeignKey('skiart.ID'))
    Art = relationship("SkiArt", backref="verleihskimodell")
    Hersteller_ID = Column(Integer, ForeignKey('verleihskihersteller.ID'))
    Hersteller = relationship("VerleihSkiHersteller", backref="verleihskimodell")

class EigenSki(Base):
    __tablename__ = "eigenski"
    ID = Column(Integer, primary_key=True)
    Modell_ID = Column(Integer, ForeignKey('verleihskimodell.ID'))
    Modell = relationship("VerleihSkiModell", backref="eigenski")
    Laenge = Column(Integer)
    VK = Column(Double)
    EK = Column(Double)
    Saison = Column(String)
    SkiNr = Column(String)