"""
validator.py
Einfache Plausibilitätsprüfungen für extrahierte Rechnungsdaten.
"""


def validate_invoice(data: dict) -> list[str]:
    """
    Prüft die extrahierten Rechnungsdaten auf Plausibilität.

    Args:
        data: Dictionary mit Rechnungsdaten (siehe parser.parse_invoice).

    Returns:
        Eine Liste von Warn-/Fehlermeldungen. Leere Liste = alles ok.
    """
    warnings = []

    required_fields = ["rechnungsnummer", "datum", "betrag_brutto"]
    for field in required_fields:
        if not data.get(field):
            warnings.append(f"Feld '{field}' konnte nicht erkannt werden.")

    netto = data.get("betrag_netto")
    mwst = data.get("mwst")
    brutto = data.get("betrag_brutto")

    if netto is not None and mwst is not None and brutto is not None:
        expected_brutto = round(netto + mwst, 2)
        if abs(expected_brutto - brutto) > 0.01:
            warnings.append(
                f"Summenprüfung fehlgeschlagen: Netto ({netto}) + MwSt. ({mwst}) "
                f"= {expected_brutto}, aber Brutto = {brutto}."
            )

    positionen = data.get("positionen", [])
    if positionen and netto is not None:
        summe_positionen = round(sum(p["gesamtpreis"] for p in positionen), 2)
        if abs(summe_positionen - netto) > 0.01:
            warnings.append(
                f"Summe der Positionen ({summe_positionen}) stimmt nicht mit "
                f"dem Nettobetrag ({netto}) überein."
            )

    return warnings


if __name__ == "__main__":
    example = {
        "rechnungsnummer": "RE-2026-001",
        "datum": "13.06.2026",
        "betrag_netto": 100.00,
        "mwst": 19.00,
        "betrag_brutto": 119.00,
        "positionen": [{"artikel": "Beratung", "menge": 2, "einzelpreis": 50.0, "gesamtpreis": 100.0}],
    }
    print(validate_invoice(example))
