from pydantic import BaseModel

from app.schemas.quittung import QuittungListeEintrag
from app.schemas.saisonverleih import SaisonVerleihRead
from app.schemas.skiservice import AuftragSchema


class KundeHistorie(BaseModel):
    """Alles, was ein Kunde bisher hatte, über alle Saisons und neueste zuerst."""
    auftraege: list[AuftragSchema]
    verleihe: list[SaisonVerleihRead]
    # Über die Aufträge und Verleihe ermittelt, also auch Sammelquittungen mit anderen Kunden
    quittungen: list[QuittungListeEintrag]
