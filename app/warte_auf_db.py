import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import dbSettings

MAX_RETRIES = 30
DELAY_SECONDS = 2


def wait_for_db() -> None:
    engine = create_engine(dbSettings.mysql_constring)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Datenbank ist bereit.")
            return
        except OperationalError:
            print(f"Datenbank noch nicht bereit (Versuch {attempt}/{MAX_RETRIES}), erneut versuchen in {DELAY_SECONDS}s...")
            time.sleep(DELAY_SECONDS)

    print("Datenbank nicht erreichbar nach max. Versuchen, breche ab.")
    sys.exit(1)


if __name__ == "__main__":
    wait_for_db()