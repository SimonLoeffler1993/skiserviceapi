from typing import Literal

# Ergebnis einer automatischen Kundenmail: None heißt, es war keine fällig (oder keine Adresse hinterlegt)
MailStatus = Literal["gesendet", "fehlgeschlagen"] | None
