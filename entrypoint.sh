#!/bin/sh
set -e

echo "Auf Datenbank warten..."
python -m app.warte_auf_db

echo "Datenbank-Migrationen ausführen..."
alembic upgrade head

# Zwischendatenbank der Check-in-App, ein Fehler dort darf die API nicht aufhalten
if [ -n "$CHECKIN_DB_HOST" ]; then
    echo "Check-in-Benutzer einrichten..."
    python -m app.checkin_benutzer || echo "WARNUNG: Check-in-Benutzer konnten nicht eingerichtet werden"

    echo "Check-in-Datenbank migrieren..."
    alembic -c alembic_checkin.ini upgrade head || echo "WARNUNG: Check-in-Datenbank konnte nicht migriert werden"
fi

echo "Datenbank Prüfen..."
python -m app.checkplzs

echo "Skiarten Prüfen und ggf. hinzufügen..."
python -m app.add_skitype

echo "Skiservice API starten..."
# Offene Terminal-Verbindungen (SSE) enden nie von selbst: beim Beenden nach 5 s schließen
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 5