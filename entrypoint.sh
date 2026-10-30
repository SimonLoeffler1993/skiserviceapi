#!/bin/sh
set -e

echo "Auf Datenbank warten..."
python -m app.warte_auf_db

echo "Datenbank-Migrationen ausführen..."
alembic upgrade head

echo "Datenbank Prüfen..."
python -m app.checkplzs

echo "Skiarten Prüfen und ggf. hinzufügen..."
python -m app.add_skitype

echo "Skiservice API starten..."
# Offene Terminal-Verbindungen (SSE) enden nie von selbst: beim Beenden nach 5 s schließen
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 5