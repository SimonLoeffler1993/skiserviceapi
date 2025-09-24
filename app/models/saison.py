from sqlalchemy import Column, Integer, String, Date
from app.db.base import Base

class Saison(Base):
    __tablename__ = "saisons"
    ID = Column(Integer, primary_key=True)
    Start = Column(Date)
    Ende = Column(Date)
    Name = Column(String(50))
    Verwendet = Column(Integer)
    SaisonVerleihNummer = Column(Integer, nullable=False, default=0)