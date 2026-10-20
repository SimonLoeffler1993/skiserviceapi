import httpx

from app.services import einstellungen


class LexwareAPI:
    # Einstellungen bei jedem Aufruf lesen, damit Änderungen im Center ohne Neustart greifen
    @property
    def baseURL(self) -> str:
        return einstellungen.hole("LEXWARE_BASEURL").rstrip("/")

    @property
    def apiKey(self) -> str:
        return einstellungen.hole("LEXWARE_APIKEY")

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
