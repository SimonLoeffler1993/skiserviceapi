from sqlalchemy import Column, Integer, String

from app.db.base import Base

# TODO Orte länger machen
class Ort(Base):
    __tablename__ = "postleitzahl"
    Postlz = Column(Integer, primary_key=True)
    Ort = Column(String(30))