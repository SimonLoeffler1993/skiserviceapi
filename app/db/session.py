from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import dbSettings

engine = create_engine(dbSettings.mysql_constring)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

