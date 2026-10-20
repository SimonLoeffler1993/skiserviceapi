from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import dbSettings

# pool_pre_ping/pool_recycle verhindern "MySQL server has gone away" nach längerer Inaktivität
engine = create_engine(dbSettings.mysql_constring, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

