from dotenv import load_dotenv
import os

# falls keine .env Datei existiert, werden die Umgebungsvariablen geladen
load_dotenv()

class DbSettings:
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", 3306))
    user = os.getenv("DB_USER", "root")
    password =  os.getenv("DB_PASSWORD", "password")
    database = os.getenv("DB_NAME", "skiservice")
    mysql_constring = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


dbSettings = DbSettings()

class PDFSettings:
    STIRLING_URL = os.getenv("STIRLING_URL", "http://pdf.fa-loeffler.de")
