"""Legt die Benutzer der Zwischendatenbank der Check-in-App an und hält sie aktuell.

Läuft bei jedem Start im Container (entrypoint.sh) vor der Check-in-Migration, ersetzt das frühere
checkin-db-init.sh. Wiederholbar: fehlende Benutzer werden angelegt, Passwörter und Rechte aus der
Umgebung übernommen, auch bei einer schon bestehenden Datenbank.

- API-Benutzer (CHECKIN_DB_USER/CHECKIN_DB_PASSWORD): alle Rechte auf die Check-in-Datenbank,
  pflegt das Schema und löscht übernommene Datensätze.
- App-Benutzer (CHECKIN_APP_USER/CHECKIN_APP_PASSWORD): darf nur einfügen und lesen, sie sieht nur Chiffretext.

Ohne CHECKIN_DB_ROOT_PASSWORD wird nichts gemacht, die Benutzer müssen dann anders angelegt sein.
"""
import os
import re
import sys
import time

import pymysql

from app.core.config import checkinDbSettings

VERSUCHE = 15
PAUSE_SEKUNDEN = 2

# Namen landen als Bezeichner im SQL, deshalb nur einfache Zeichen
NAME_MUSTER = re.compile(r"^[A-Za-z0-9_]{1,32}$")


def pruefe_name(art: str, name: str) -> None:
    if not NAME_MUSTER.match(name):
        raise ValueError(f"{art} '{name}' ist ungültig, erlaubt sind Buchstaben, Ziffern und _")


def verbinden(root_user: str, root_passwort: str) -> pymysql.Connection:
    for versuch in range(1, VERSUCHE + 1):
        try:
            return pymysql.connect(
                host=checkinDbSettings.host,
                port=checkinDbSettings.port,
                user=root_user,
                password=root_passwort,
                autocommit=True,
            )
        except pymysql.err.OperationalError as fehler:
            if versuch == VERSUCHE:
                raise
            print(f"Check-in-Datenbank noch nicht bereit ({versuch}/{VERSUCHE}): {fehler.args[-1]}")
            time.sleep(PAUSE_SEKUNDEN)
    raise RuntimeError("nicht erreichbar")


def benutzer_einrichten(cur, name: str, passwort: str, rechte: str, datenbank: str) -> None:
    # Immer mit Parametern ausführen, damit PyMySQL formatiert: %% wird dabei zum Host-Platzhalter %
    konto = f"'{name}'@'%%'"
    cur.execute(f"CREATE USER IF NOT EXISTS {konto} IDENTIFIED BY %s", (passwort,))
    # Passwort aus der Umgebung übernehmen, auch wenn der Benutzer schon existierte
    cur.execute(f"ALTER USER {konto} IDENTIFIED BY %s", (passwort,))
    # Rechte immer neu setzen, damit der App-Benutzer nie mehr als einfügen und lesen darf
    cur.execute(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM {konto}", ())
    cur.execute(f"GRANT {rechte} ON `{datenbank}`.* TO {konto}", ())


def main() -> int:
    if not checkinDbSettings.host:
        print("CHECKIN_DB_HOST nicht gesetzt, Check-in-Benutzer werden nicht eingerichtet.")
        return 0

    root_passwort = os.getenv("CHECKIN_DB_ROOT_PASSWORD") or ""
    if not root_passwort:
        print("CHECKIN_DB_ROOT_PASSWORD nicht gesetzt, Check-in-Benutzer werden nicht eingerichtet.")
        return 0

    root_user = (os.getenv("CHECKIN_DB_ROOT_USER") or "root").strip()
    datenbank = checkinDbSettings.database
    api_user = checkinDbSettings.user
    api_passwort = checkinDbSettings.password
    app_user = (os.getenv("CHECKIN_APP_USER") or "checkin_app").strip()
    app_passwort = os.getenv("CHECKIN_APP_PASSWORD") or ""

    pruefe_name("Datenbankname", datenbank)
    pruefe_name("CHECKIN_DB_USER", api_user)
    pruefe_name("CHECKIN_APP_USER", app_user)
    if api_user == app_user:
        raise ValueError("CHECKIN_DB_USER und CHECKIN_APP_USER müssen verschieden sein")
    if not api_passwort:
        raise ValueError("CHECKIN_DB_PASSWORD ist leer")
    if not app_passwort:
        raise ValueError("CHECKIN_APP_PASSWORD ist leer")
    # Die Check-in-App bekommt das Passwort in ihrer DATABASE_URL, Sonderzeichen würden die URL brechen
    if not re.fullmatch(r"[A-Za-z0-9]+", app_passwort):
        print("WARNUNG: CHECKIN_APP_PASSWORD enthält Sonderzeichen, in der DATABASE_URL der App nur Buchstaben und Ziffern verwenden.")

    verbindung = verbinden(root_user, root_passwort)
    try:
        with verbindung.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{datenbank}`")
            if api_user != root_user:
                benutzer_einrichten(cur, api_user, api_passwort, "ALL PRIVILEGES", datenbank)
            benutzer_einrichten(cur, app_user, app_passwort, "INSERT, SELECT", datenbank)
    finally:
        verbindung.close()

    print(f"Check-in-Benutzer eingerichtet: {api_user} (alle Rechte), {app_user} (einfügen, lesen).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as fehler:  # noqa: BLE001 – Meldung reicht, entrypoint.sh entscheidet über den Abbruch
        print(f"FEHLER beim Einrichten der Check-in-Benutzer: {fehler}")
        sys.exit(1)
