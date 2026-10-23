"""
GiroCode (EPC QR-Code) für SEPA Überweisungen, Standard EPC069-12.
Banking-Apps lesen daraus Empfänger, IBAN, Betrag und Verwendungszweck.
"""
import base64
import io
import re

import qrcode


# Im SEPA Verwendungszweck sicher erlaubte Zeichen (lateinischer Zeichensatz der SEPA Spezifikation)
_NICHT_SEPA = re.compile(r"[^A-Za-z0-9/\-?:().,'+ ]")


def sepa_text(text: str) -> str:
    """Umlaute umschreiben, alle anderen nicht erlaubten Zeichen durch Leerzeichen ersetzen."""
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"), ("·", "-")):
        text = text.replace(alt, neu)
    return re.sub(r" {2,}", " ", _NICHT_SEPA.sub(" ", text)).strip()


def girocode_daten(name: str, iban: str, bic: str | None, betrag: float, zweck: str) -> str:
    """Inhalt des QR-Codes: Version 002 (BIC optional), UTF-8, SEPA Credit Transfer."""
    zeilen = [
        "BCD",
        "002",
        "1",                                  # UTF-8
        "SCT",
        (bic or "").replace(" ", "").upper(),
        name.strip()[:70],
        iban.replace(" ", "").upper(),
        f"EUR{betrag:.2f}",
        "",                                   # Zweck (Purpose Code)
        "",                                   # strukturierte Referenz
        sepa_text(zweck)[:140],               # unstrukturierter Verwendungszweck
    ]
    return "\n".join(zeilen)


def girocode_png_data_uri(name: str, iban: str, bic: str | None, betrag: float, zweck: str) -> str:
    """QR-Code als PNG data: URI, z.B. für <img> im PDF Template."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(girocode_daten(name, iban, bic, betrag, zweck))
    qr.make(fit=True)
    puffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(puffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(puffer.getvalue()).decode()


def iban_formatiert(iban: str) -> str:
    """DE89370400440532013000 -> DE89 3704 0044 0532 0130 00"""
    iban = iban.replace(" ", "").upper()
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))
