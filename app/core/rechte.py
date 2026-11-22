"""
Feste Rechteliste. Rollen bündeln Rechte, Gruppen bekommen Rollen, Benutzer sind Mitglied in Gruppen.
Lesen darf jeder angemeldete Benutzer; die Rechte steuern Schreiben, Löschen und Verwalten.

Die Systemrolle "Administrator" hat ALLE_RECHTE ("*"), auch Rechte, die später dazukommen.
"""

ALLE_RECHTE = "*"

# Recht -> (Bereich, Bezeichnung)
RECHTE: dict[str, tuple[str, str]] = {
    "skiservice.anlegen": ("Skiservice", "Neue Aufträge anlegen"),
    "skiservice.bearbeiten": ("Skiservice", "Aufträge ändern: Daten, Ski hinzufügen, ändern und entfernen, Bindungsdaten, bezahlt von Hand"),
    "skiservice.status": ("Skiservice", "Ski fertig, Bindung geprüft, abgeholt, Kunden benachrichtigen"),
    "skiservice.loeschen": ("Skiservice", "Aufträge löschen"),
    "verleih.anlegen": ("Verleih", "Neue Verleihe anlegen (Saison und Tag)"),
    "verleih.bearbeiten": ("Verleih", "Verleihe ändern: Daten, Material hinzufügen, ändern und entfernen, bezahlt von Hand"),
    "verleih.status": ("Verleih", "Status, Bindung geprüft, Zurückgeben, Kunden benachrichtigen"),
    "verleih.loeschen": ("Verleih", "Verleihe löschen"),
    "kunden.anlegen": ("Kunden", "Neue Kunden anlegen, Check-in übernehmen und verwerfen"),
    "kunden.bearbeiten": ("Kunden", "Kunden ändern, Kunde ans Terminal senden"),
    "material.bearbeiten": ("Material", "Ski, Schuhe, Stöcke, Hersteller, Modelle und Services am Leihski"),
    "kasse.kassieren": ("Kasse", "Kasse bedienen, Quittung per Mail senden"),
    "quittungen.verwalten": ("Kasse", "Quittungen stornieren, aus Quittung entfernen, Lexware-Upload, externe Belege"),
    "preise.verwalten": ("Verwaltung", "Preise für Skiservice und Verleih, Bindungsservice, Handware"),
    "vorlagen.verwalten": ("Verwaltung", "Mail-Vorlagen"),
    "einstellungen.verwalten": ("Verwaltung", "Einstellungen, Check-in-Schlüssel, neue Saison"),
    "benutzer.verwalten": ("Verwaltung", "Benutzer, Gruppen und Rollen, Freigaben, Verlauf je Benutzer"),
    "geraete.verwalten": ("Verwaltung", "Geräteschlüssel, angemeldete Geräte, Scanner-Update"),
    "geraete.anmelden": ("Verwaltung", "Geräte (Center, Kasse) dauerhaft anmelden: danach Bedienerauswahl und PIN"),
}

# Rechte der bisherigen Rolle "Mitarbeiter" (Migration und neue Installation)
MITARBEITER_RECHTE = [
    "skiservice.anlegen", "skiservice.bearbeiten", "skiservice.status",
    "verleih.anlegen", "verleih.bearbeiten", "verleih.status",
    "kunden.anlegen", "kunden.bearbeiten", "material.bearbeiten", "kasse.kassieren",
]

# Fertige Rolle mit nur diesem Recht (Migration und neue Installation)
GERAET_ANMELDEN = "geraete.anmelden"
ROLLE_GERAET_ANMELDEN = "Gerät anmelden"

SYSTEMROLLE = "Administrator"
ADMIN_GRUPPE = "Administratoren"

# Mit diesem Recht kann man sich immer selbst wieder Rechte geben: davon muss ein Notzugang bleiben
VERWALTUNGSRECHT = "benutzer.verwalten"


def hat(rechte: frozenset[str] | set[str], recht: str) -> bool:
    return ALLE_RECHTE in rechte or recht in rechte
