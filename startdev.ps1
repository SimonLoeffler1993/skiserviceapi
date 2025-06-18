# Name der Conda-Umgebung
$envName = "skiserviceapi"

# Projektordner mit der FastAPI-App
# $projectDir = "app"

# Uvicorn-Startbefehl (hier: main.py enthält die FastAPI-Instanz "app")
$uvicornCommand = "uvicorn app.main:app --reload"

# Initialisiere conda (falls nötig)
conda activate $envName

# Wechsel in das App-Verzeichnis
# Set-Location $projectDir

# Starte FastAPI mit Uvicorn im Entwicklungsmodus
Invoke-Expression $uvicornCommand
