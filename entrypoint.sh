#!/bin/sh
set -e

echo "Auf Datenbank warten..."
python -m app.warte_auf_db

echo "Datenbank-Migrationen ausführen..."
alembic upgrade head

echo "Skiservice API starten..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000