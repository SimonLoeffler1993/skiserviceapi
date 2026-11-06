from dotenv import load_dotenv
from sqlalchemy import URL
import os

# falls keine .env Datei existiert, werden die Umgebungsvariablen geladen
load_dotenv()

def env_int(name: str, standard: int) -> int:
    """Liest eine Zahl aus der Umgebung; leere oder ungültige Werte ergeben den Standardwert."""
    wert = (os.getenv(name) or "").strip()
    try:
        return int(wert) if wert else standard
    except ValueError:
        return standard

# Nur die Datenbank wird über Umgebungsvariablen eingestellt.
# Alle anderen Einstellungen stehen in der Datenbank, siehe app/services/einstellungen.py
class DbSettings:
    host = os.getenv("DB_HOST", "localhost")
    port = env_int("DB_PORT", 3306)
    user = os.getenv("DB_USER", "root")
    password =  os.getenv("DB_PASSWORD", "password")
    database = os.getenv("DB_NAME", "skiservice")
    # URL.create maskiert Sonderzeichen im Passwort
    mysql_constring = URL.create(
        "mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
    )


dbSettings = DbSettings()


# Zwischendatenbank der Check-in-App, optional: ohne Host gilt der Check-in als nicht eingerichtet
class CheckinDbSettings:
    host = (os.getenv("CHECKIN_DB_HOST") or "").strip()
    port = env_int("CHECKIN_DB_PORT", 3306)
    user = os.getenv("CHECKIN_DB_USER", "checkin")
    password = os.getenv("CHECKIN_DB_PASSWORD", "")
    database = os.getenv("CHECKIN_DB_NAME", "checkin")
    url = URL.create(
        "mysql+pymysql",
        username=user,
        password=password,
        host=host or "localhost",
        port=port,
        database=database,
    )


checkinDbSettings = CheckinDbSettings()

# Gemeinsames Volume: Die API schreibt den aktuellen Public Key hinein, die Check-in-App liest ihn nur
checkinPublicKeyOrdner = (os.getenv("CHECKIN_PUBLIC_KEY_ORDNER") or "").strip()
