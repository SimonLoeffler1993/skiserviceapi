"""
Notzugang, falls sich alle ausgesperrt haben.

    docker exec -it <api> python -m app.benutzer_notfall --anmeldung-aus
    docker exec -it <api> python -m app.benutzer_notfall --benutzer admin --passwort 'NeuesPasswort'
    docker exec -it <api> python -m app.benutzer_notfall --benutzer admin --admin --passwort '…'   (legt an, falls nicht vorhanden)

--passwort setzt das Passwort, entsperrt und aktiviert den Benutzer; mit --admin kommt er in die Admin-Gruppe.
--anmeldung-aus schaltet ANMELDUNG_ERZWINGEN aus (Center und Kasse wieder ohne Anmeldung nutzbar).
"""
import argparse
import sys
from datetime import datetime

from app.core import sicherheit
from app.crud import rechte as crud_rechte
from app.db.session import SessionLocal
from app.models.benutzer import Benutzer
from app.services import einstellungen


def main() -> int:
    parser = argparse.ArgumentParser(description="Notzugang Benutzerverwaltung")
    parser.add_argument("--benutzer", help="Benutzername")
    parser.add_argument("--passwort", help="Neues Passwort (muss nach der Anmeldung geändert werden)")
    parser.add_argument("--admin", action="store_true", help="Benutzer zum Admin machen bzw. als Admin anlegen")
    parser.add_argument("--anmeldung-aus", action="store_true", help="ANMELDUNG_ERZWINGEN ausschalten")
    args = parser.parse_args()

    if not args.anmeldung_aus and not (args.benutzer and args.passwort):
        parser.print_help()
        return 1

    with SessionLocal() as db:
        if args.anmeldung_aus:
            einstellungen.speichern(db, {"ANMELDUNG_ERZWINGEN": False})
            print("ANMELDUNG_ERZWINGEN ist aus. Die API muss ggf. neu gestartet werden, damit der Cache leer ist.")

        if args.benutzer and args.passwort:
            benutzer = db.query(Benutzer).filter(Benutzer.Benutzername == args.benutzer).one_or_none()
            if benutzer is None:
                if not args.admin:
                    print(f"Benutzer „{args.benutzer}“ gibt es nicht. Mit --admin wird er angelegt.")
                    return 1
                benutzer = Benutzer(Benutzername=args.benutzer, Anzeigename=args.benutzer, Angelegt_Am=datetime.now())
                db.add(benutzer)
            benutzer.Passwort_Hash = sicherheit.passwort_hash(args.passwort)
            benutzer.Passwort_Aendern = True
            benutzer.Aktiv = True
            benutzer.Freigabe_Ausstehend = False
            benutzer.Fehlversuche = 0
            benutzer.Gesperrt_Bis = None
            if args.admin:
                db.flush()
                crud_rechte.zur_admin_gruppe(db, benutzer)
            db.commit()
            zusatz = " und Mitglied der Admin-Gruppe" if args.admin else ""
            print(f"Passwort für „{benutzer.Benutzername}“ gesetzt, Benutzer entsperrt, aktiv{zusatz}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
