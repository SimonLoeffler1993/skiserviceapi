from datetime import date
from decimal import Decimal


def datum(wert) -> str:
    """'2026-10-18' / date / datetime -> '18.10.2026'"""
    if not wert:
        return ""
    if isinstance(wert, str):
        wert = date.fromisoformat(wert[:10])
    return wert.strftime("%d.%m.%Y")


def eur(wert) -> str:
    """1234.5 -> '1.234,50 €'"""
    text = f"{Decimal(str(wert or 0)):,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".") + " €"
