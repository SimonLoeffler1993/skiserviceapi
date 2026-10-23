import logging
import time

import httpx

from app.services import einstellungen

logger = logging.getLogger(__name__)


class LexwareFehler(Exception):
    """Lexware nicht erreichbar oder Anfrage abgelehnt, mit lesbarer Meldung."""

    def __init__(self, meldung: str, status_code: int | None = None):
        super().__init__(meldung)
        self.status_code = status_code


def _dateiname(content_disposition: str | None) -> str | None:
    """Dateiname aus 'attachment; filename="RE1019.pdf"'"""
    if not content_disposition or "filename=" not in content_disposition:
        return None
    return content_disposition.split("filename=", 1)[1].split(";")[0].strip().strip('"') or None


class LexwareAPI:
    # Einstellungen bei jedem Aufruf lesen, damit Änderungen im Center ohne Neustart greifen
    @property
    def baseURL(self) -> str:
        return einstellungen.hole("LEXWARE_BASEURL").rstrip("/")

    @property
    def apiKey(self) -> str:
        return einstellungen.hole("LEXWARE_APIKEY")

    def _header(self, accept: str = "application/json") -> dict:
        return {"Accept": accept, "Authorization": f"Bearer {self.apiKey}"}

    def _senden(self, methode: str, pfad: str, accept: str = "application/json", **kwargs) -> httpx.Response:
        """
        Anfrage an Lexware. Bei 429 (mehr als 2 Anfragen pro Sekunde) wird einmal nach 1 s wiederholt.
        Fehler werden in LexwareFehler mit Meldung von Lexware umgewandelt.
        """
        if not self.apiKey:
            raise LexwareFehler("Kein Lexware API Key hinterlegt.")
        url = f"{self.baseURL}{pfad}"
        try:
            for versuch in range(2):
                response = httpx.request(methode, url, headers=self._header(accept), timeout=30, **kwargs)
                if response.status_code == 429 and versuch == 0:
                    time.sleep(1)
                    continue
                break
        except httpx.HTTPError as e:
            raise LexwareFehler(f"Lexware nicht erreichbar: {e}") from e
        if response.is_error:
            try:
                detail = response.json().get("message") or response.text
            except ValueError:
                detail = response.text
            logger.error("Lexware %s %s -> %s: %s", methode, pfad, response.status_code, response.text[:1000])
            raise LexwareFehler(f"Lexware hat die Anfrage abgelehnt ({response.status_code}): {detail[:300]}",
                                response.status_code)
        return response

    def _anfrage(self, methode: str, pfad: str, **kwargs) -> dict:
        response = self._senden(methode, pfad, **kwargs)
        return response.json() if response.content else {}

    def erstelle_beleg(self, daten: dict) -> dict:
        """Buchhaltungsbeleg (Voucher) anlegen, gibt u.a. die id zurück."""
        return self._anfrage("POST", "/v1/vouchers", json=daten)

    def lade_beleg_datei_hoch(self, beleg_id: str, pdf: bytes, dateiname: str) -> dict:
        """PDF an einen Beleg anhängen."""
        return self._anfrage("POST", f"/v1/vouchers/{beleg_id}/files", files={"file": (dateiname, pdf, "application/pdf")})

    def erstelle_rechnung(self, daten: dict) -> dict:
        """Rechnung anlegen und direkt finalisieren (Status open)."""
        return self._anfrage("POST", "/v1/invoices", params={"finalize": "true"}, json=daten)

    def hole_rechnung(self, rechnung_id: str) -> dict:
        return self._anfrage("GET", f"/v1/invoices/{rechnung_id}")

    def hole_rechnung_pdf(self, rechnung_id: str) -> tuple[bytes, str | None]:
        """
        PDF einer Rechnung und der von Lexware vorgeschlagene Dateiname.
        Ist das PDF noch nicht gerendert (z.B. frisch per API angelegt), wird es einmal über den
        älteren /document Aufruf erzeugt und über den Files Endpunkt geladen.
        """
        try:
            response = self._senden("GET", f"/v1/invoices/{rechnung_id}/file", accept="application/pdf")
        except LexwareFehler as e:
            if e.status_code not in (404, 406, 409):
                raise
            datei_id = self._anfrage("GET", f"/v1/invoices/{rechnung_id}/document").get("documentFileId")
            if not datei_id:
                raise LexwareFehler("Lexware hat für die Rechnung kein PDF erzeugt.") from e
            response = self._senden("GET", f"/v1/files/{datei_id}", accept="application/pdf")
        return response.content, _dateiname(response.headers.get("content-disposition"))

    def get_customers(self):
        # Hier könnte die Logik implementiert werden, um Kunden von der Lexware API abzurufen
        pass

    def create_invoice(self, invoice_data):
        # Hier könnte die Logik implementiert werden, um eine Rechnung über die Lexware API zu erstellen
        pass

    def get_bezahlstatus(self, invoice_id):
        url = f"{self.baseURL}/v1/payments/{invoice_id}"
        headers = {
            "cache-control": "no-cache",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.apiKey}"
            }
        response = httpx.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    
    def get_belege(self, page: int = 0):
        # TODO: #4 Belege mit Filterung nach Typ und Status abrufen von Lexware API
        url = f"{self.baseURL}/v1/voucherlist?voucherType=invoice&voucherStatus=any&page={page}"
        headers = {
            "cache-control": "no-cache",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.apiKey}"
            }
        response = httpx.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_profil(self):
        """Firmenprofil abrufen, wird zum Testen des API Keys verwendet."""
        url = f"{self.baseURL}/v1/profile"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.apiKey}"
            }
        response = httpx.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
