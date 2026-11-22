"""
CORS nach der Einstellung ERLAUBTE_URSPRUENGE (Adressen von Center und Kasse).
Leer = alle Seiten erlaubt (wie bisher). Zugangsdaten gehen als Header, nie als Cookie: keine Credentials.
"""
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from app.services import einstellungen


class EinstellungsCors(CORSMiddleware):
    def __init__(self, app: ASGIApp):
        # Ohne "*" spiegelt Starlette die erlaubte Origin zurück und fragt dafür is_allowed_origin
        super().__init__(app, allow_origins=[], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

    def is_allowed_origin(self, origin: str) -> bool:
        erlaubt = einstellungen.urspruenge()
        return not erlaubt or origin.rstrip("/").lower() in [u.lower() for u in erlaubt]
