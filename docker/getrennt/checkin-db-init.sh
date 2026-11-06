#!/bin/bash
# Läuft nur beim allerersten Start der Zwischendatenbank.
# Die Check-in-App darf einfügen und lesen (sie sieht nur Chiffretext), aber nichts löschen oder ändern.
# Die API pflegt das Schema und löscht übernommene Datensätze.
set -e
mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" <<SQL
CREATE USER 'checkin_app'@'%' IDENTIFIED BY '$CHECKIN_APP_PASSWORD';
GRANT INSERT, SELECT ON \`checkin\`.* TO 'checkin_app'@'%';
CREATE USER 'checkin_api'@'%' IDENTIFIED BY '$CHECKIN_API_PASSWORD';
GRANT ALL PRIVILEGES ON \`checkin\`.* TO 'checkin_api'@'%';
FLUSH PRIVILEGES;
SQL
