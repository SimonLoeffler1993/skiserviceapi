import httpx

from app.core.config import LexwareSettings


class LexwareAPI:
    def __init__(self):
        self.baseURL = LexwareSettings.baseURl
        self.apiKey = LexwareSettings.apiKey

    def get_customers(self):
        # Hier könnte die Logik implementiert werden, um Kunden von der Lexware API abzurufen
        pass

    def create_invoice(self, invoice_data):
        # Hier könnte die Logik implementiert werden, um eine Rechnung über die Lexware API zu erstellen
        pass

    def get_bezahlstatus(self, invoice_id):
        print(self.apiKey)
        url = f"{self.baseURL}/v1/payments/{invoice_id}"
        headers = {
            "cache-control": "no-cache",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.apiKey}"
            }
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
