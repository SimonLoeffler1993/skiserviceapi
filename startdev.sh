#!/bin/bash

# Name der virtuellen Umgebung
venvPath=".venv"

# Projektordner mit der FastAPI-App
# projectDir="app"

# Uvicorn-Startbefehl (hier: main.py enthält die FastAPI-Instanz "app")
# Offene Terminal-Verbindungen (SSE) beim Neuladen nach 5 s schließen, sonst hängt --reload
uvicornCommand="uvicorn app.main:app --reload --timeout-graceful-shutdown 5"

# Aktiviere die virtuelle Umgebung
source $venvPath/bin/activate

# Wechsel in das App-Verzeichnis
# cd $projectDir

# Starte FastAPI mit Uvicorn im Entwicklungsmodus
eval $uvicornCommand
