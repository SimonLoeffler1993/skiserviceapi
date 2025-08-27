from sqlalchemy import Column, Integer, String, ForeignKey, Double
from sqlalchemy.orm import relationship

from app.db.base import Base

# TODO: Unterscheidung zwischen Kinder und Erwachsenenschuhen

class VerleihSchuhHersteller(Base):
    __tablename__ = "verleihschuhhersteller"
    ID = Column(Integer, primary_key=True)
    Name = Column(String)

class VerleihSchuhModell(Base):
    __tablename__ = "verleihschuhmodell"
    ID = Column(Integer, primary_key=True)
    Modell = Column(String)
    Jugend = Column(Integer)
    Hersteller_ID = Column(Integer, ForeignKey('verleihschuhhersteller.ID'))
    Hersteller = relationship("VerleihSchuhHersteller", backref="verleihschuhmodell")

class EigenSchuh(Base):
    __tablename__ = "eigenschuh"
    ID = Column(Integer, primary_key=True)
    Modell_ID = Column(Integer, ForeignKey('verleihschuhmodell.ID'))
    Modell = relationship("VerleihSchuhModell", backref="eigenschuh")
    Groese = Column(Double)
    Saison = Column(String)
    VK = Column(Double)
    EK = Column(Double)