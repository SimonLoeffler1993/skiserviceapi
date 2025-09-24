from app.db.base import Base
from sqlalchemy import Column, Integer, String

class Skistock(Base):
    __tablename__ = "verleihstocke"
    ID = Column(Integer, primary_key=True)
    Bezeichnung = Column(String, nullable=False)