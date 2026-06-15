"""
parser.py
Erkennt aus dem Rohtext einer Rechnung strukturierte Felder mithilfe von
regulären Ausdrücken: Rechnungsnummer, Datum, Lieferant, Beträge, IBAN,
sowie Rechnungspositionen.
"""

import re

# Amount in German format (1.234,56 / 1234,56) OR international format
# (1,234.56 / 1234.56 / 13.85). Group 1 captures the full numeric string
# including separators.
AMOUNT = r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2})"

# Currency symbols and ISO codes that may appear before or after an amount.
# Used both to recognize amounts with arbitrary currencies and to detect
# the overall currency of an invoice.
CURRENCY_SYMBOL = r"(?:€|\$|£|CHF|EUR|USD|GBP|Fr\.)"

# Maps recognized symbols/codes to a normalized 3-letter currency code.
_CURRENCY_MAP = {
    "€": "EUR",
    "EUR": "EUR",
    "$": "USD",
    "USD": "USD",
    "£": "GBP",
    "GBP": "GBP",
    "CHF": "CHF",
    "FR.": "CHF",
}


def parse_invoice(text: str) -> dict:
    """
    Extrahiert strukturierte Rechnungsdaten aus dem Rohtext.

    Args:
        text: Der mit extractor.extract_text_from_pdf() gewonnene Rohtext.

    Returns:
        Ein Dictionary mit den erkannten Feldern. Felder, die nicht
        gefunden wurden, enthalten None.
    """
    data = {
        "rechnungsnummer": _extract_rechnungsnummer(text),
        "datum": _extract_datum(text),
        "lieferant": _extract_lieferant(text),
        "betrag_netto": _extract_betrag(text, "netto"),
        "mwst": _extract_betrag(text, "mwst"),
        "betrag_brutto": _extract_betrag(text, "brutto"),
        "currency": _extract_currency(text),
        "iban": _extract_iban(text),
        "positionen": _extract_positionen(text),
    }
    return data


def _extract_rechnungsnummer(text: str) -> str | None:
    pattern = (
        r"(?:Rechnungs?\s*-?\s*(?:Nr\.?|nummer)|Rechnung|Invoice\s*(?:No\.?|Number)|Beleg\s*(?:-?Nr\.?|nummer)?)"
        r"[:\s]*([A-Za-z0-9][A-Za-z0-9\-/]*\d[A-Za-z0-9\-/]*)"
    )
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_datum(text: str) -> str | None:
    # Bevorzugt: explizit als "Datum:" / "Rechnungsdatum:" markiertes Datum
    pattern_labeled = r"(?:Rechnungs?datum|Datum)[:\s]*(\d{1,2}\.\d{1,2}\.\d{2,4})"
    match = re.search(pattern_labeled, text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Fallback: erstes beliebige Datum im deutschen Format TT.MM.JJJJ
    pattern = r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b"
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _extract_lieferant(text: str) -> str | None:
    # Heuristik: oft steht der Firmenname mit Rechtsform (GmbH, AG, e.K. etc.)
    # in einer der ersten Zeilen.
    pattern = r"^(.*?(?:GmbH|AG|KG|e\.K\.|UG|OHG|GbR))\b"
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_currency(text: str) -> str:
    """
    Detects the currency used in the invoice by counting occurrences of
    known currency symbols/codes (€, $, £, CHF, EUR, USD, GBP, Fr.) and
    returning the most frequent one as a normalized 3-letter code.

    Falls back to "EUR" if no currency indicator is found, since this is
    the most common case for the supported invoice layouts.
    """
    matches = re.findall(CURRENCY_SYMBOL, text, re.IGNORECASE)
    if not matches:
        return "EUR"

    counts: dict[str, int] = {}
    for match in matches:
        code = _CURRENCY_MAP.get(match.upper(), _CURRENCY_MAP.get(match, "EUR"))
        counts[code] = counts.get(code, 0) + 1

    return max(counts, key=counts.get)


def _extract_betrag(text: str, kind: str) -> float | None:
    """
    Sucht nach Geldbeträgen (deutsches oder internationales Zahlenformat,
    z.B. 1.234,56 € oder 1234.56) für die Kategorien 'netto', 'mwst'
    (oder 'ust') und 'brutto'. Das Euro-Zeichen kann vor oder nach dem
    Betrag stehen.
    """
    keywords = {
        "netto": r"(?:Netto(?:betrag)?|Zwischensumme|Summe\s+Netto)",
        "mwst": r"(?:MwSt\.?|USt\.?|Umsatzsteuer)(?:\s*\(?\d{1,2}(?:[.,]\d{1,2})?\s*%\)?)?(?:\s+auf\s+[\d.,]+\s*€?)?",
        "brutto": r"(?:Brutto(?:betrag)?|Gesamtbetrag|Gesamt(?:summe)?|Rechnungsbetrag|Endbetrag|End-?summe)",
    }

    # Amount with an optional currency symbol/code before or after it
    amount_pattern = rf"(?:{CURRENCY_SYMBOL}\s*)?{AMOUNT}\s*{CURRENCY_SYMBOL}?"
    pattern = rf"{keywords[kind]}[:\s]*{amount_pattern}"

    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None

    return _to_float(match.group(1))


def _extract_iban(text: str) -> str | None:
    # Sucht explizit nach "IBAN" gefolgt von einem IBAN-ähnlichen Muster
    # (Länderkennung + Prüfziffern + bis zu 30 alphanumerische Zeichen,
    # ggf. durch Leerzeichen gruppiert).
    pattern = r"IBAN[:\s]*([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{1,4}){2,9})"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        iban = match.group(1).replace(" ", "")
        return iban.upper()

    # Fallback: IBAN-ähnliches Muster ohne Schlüsselwort
    pattern = r"\b([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}\s?[A-Z0-9]{0,3})\b"
    match = re.search(pattern, text)
    if match:
        return match.group(1).replace(" ", "")
    return None


def _extract_positionen(text: str) -> list[dict]:
    """
    Erkennt Rechnungspositionen, indem zunächst der Tabellenbereich anhand
    von Schlüsselwörtern abgegrenzt wird:

    - Tabellenstart: eine Zeile, die wie eine Tabellen-Kopfzeile aussieht
      (enthält z.B. "Bezeichnung"/"Artikel"/"Beschreibung" UND
      "Menge"/"Anzahl" UND "Preis"/"Gesamt").
    - Tabellenende: die erste Zeile danach, die mit einem Summen-Schlüsselwort
      beginnt ("Summe", "Zwischensumme", "Gesamt", "Endsumme", ...).

    Innerhalb dieses Bereichs wird jede Zeile generisch (spaltenbasiert)
    interpretiert: die letzten zwei Geldbeträge in der Zeile sind
    Einzelpreis und Gesamtpreis, ein davor stehender Wert mit optionaler
    Einheit ist die Menge, der Rest der Zeile (ggf. nach einer führenden
    Positions-/Artikelnummer) ist die Artikelbezeichnung.

    Dieser Ansatz ist bewusst layout-unabhängig gehalten, um neue
    Rechnungsformate ohne zusätzliche feste Zeilen-Patterns abzudecken.
    Bei sehr unüblichen Layouts (z.B. mehrzeilige Tabellenzellen) kann
    es trotzdem nötig sein, extract_tables_from_pdf() als Ergänzung
    zu nutzen.
    """
    lines = [line.strip() for line in text.splitlines()]

    start_idx = _find_table_start(lines)
    if start_idx is None:
        return []

    end_idx = _find_table_end(lines, start_idx + 1)

    positionen = []
    category_heading = r"^\d+\.\s+[A-Za-zÄÖÜäöüß]+$"
    zwischensumme = r"^(?:Summe|Zwischensumme)\b"

    for line in lines[start_idx + 1:end_idx]:
        if not line:
            continue
        if re.match(category_heading, line) or re.match(zwischensumme, line, re.IGNORECASE):
            continue
        pos = _parse_positionszeile(line)
        if pos:
            positionen.append(pos)

    return positionen


def _find_table_start(lines: list[str]) -> int | None:
    """Findet die Zeile, die wie eine Tabellen-Kopfzeile aussieht."""
    bezeichnung_keywords = r"(?:Bezeichnung|Artikel|Beschreibung|Leistung|Position)"
    menge_keywords = r"(?:Menge|Anzahl|Stück)"
    preis_keywords = r"(?:Preis|Gesamt|Betrag|Summe)"

    for i, line in enumerate(lines):
        if (re.search(bezeichnung_keywords, line, re.IGNORECASE)
                and re.search(menge_keywords, line, re.IGNORECASE)
                and re.search(preis_keywords, line, re.IGNORECASE)):
            return i

    return None


def _find_table_end(lines: list[str], start: int) -> int:
    """
    Findet die erste Zeile ab `start`, die das Tabellenende markiert.

    Eine Zeile, die mit "Summe"/"Zwischensumme"/... beginnt, markiert das
    Tabellenende - AUSSER es handelt sich um eine kategoriebezogene
    Zwischensumme (z.B. "Summe Material: 1.224,90 €"), auf die direkt eine
    neue Kategorie-Überschrift folgt (z.B. "2. Arbeit"). In diesem Fall
    geht die Tabelle weiter.

    Falls keine endgültige Summenzeile gefunden wird, wird das Ende der
    Liste zurückgegeben.
    """
    end_keywords = (
        r"^(?:Summe|Zwischensumme|Gesamt(?:summe)?|Endsumme|Netto(?:betrag)?|"
        r"Brutto(?:betrag)?|Rechnungsbetrag)\b"
    )
    category_heading = r"^\d+\.\s+[A-Za-zÄÖÜäöüß]+$"

    for i in range(start, len(lines)):
        if re.match(end_keywords, lines[i], re.IGNORECASE):
            # Prüfen, ob direkt danach eine neue Kategorie-Überschrift folgt
            # (= diese "Summe"-Zeile war nur eine Zwischensumme)
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if re.match(category_heading, next_line):
                continue
            return i

    return len(lines)


def _parse_positionszeile(line: str) -> dict | None:
    """
    Parst eine einzelne Tabellenzeile spaltenbasiert:

    - Findet alle Geldbeträge im deutschen Format (z.B. 1.234,56) in der Zeile.
    - Die letzten zwei davon werden als Einzelpreis und Gesamtpreis interpretiert
      (bei nur einem Betrag: dieser wird als Gesamtpreis verwendet, Menge = 1).
    - Vor diesen Beträgen wird nach einer Mengenangabe gesucht (Zahl, optional
      mit Einheit wie "Stk."/"Std."/"Eimer").
    - Der verbleibende Text davor (ggf. nach einer führenden Positions-/
      Artikelnummer) ist die Artikelbezeichnung.

    Gibt None zurück, wenn die Zeile nicht wie eine Positionszeile aussieht
    (z.B. weniger als ein Geldbetrag vorhanden, oder es bleibt keine
    Artikelbezeichnung übrig).
    """
    amounts = list(re.finditer(rf"{CURRENCY_SYMBOL}?\s*{AMOUNT}\s*{CURRENCY_SYMBOL}?", line, re.IGNORECASE))

    if not amounts:
        return None

    # Letzte zwei Beträge = Einzelpreis und Gesamtpreis (oder nur Gesamtpreis)
    if len(amounts) >= 2:
        einzelpreis_match, gesamtpreis_match = amounts[-2], amounts[-1]
        einzelpreis = _to_float(einzelpreis_match.group(1))
        gesamtpreis = _to_float(gesamtpreis_match.group(1))
        rest_ende = einzelpreis_match.start()
    else:
        gesamtpreis_match = amounts[-1]
        gesamtpreis = _to_float(gesamtpreis_match.group(1))
        einzelpreis = gesamtpreis
        rest_ende = gesamtpreis_match.start()

    rest = line[:rest_ende].strip()

    # Menge (mit optionaler Einheit) am Ende des verbleibenden Texts suchen
    menge = 1.0
    menge_pattern = rf"({AMOUNT}|\d+)\s*(?:[A-Za-zÄÖÜäöüß]+\.?)?\s*$"
    menge_match = re.search(menge_pattern, rest)
    if menge_match:
        menge_str = menge_match.group(1)
        try:
            menge = _to_float(menge_str) if ("," in menge_str or "." in menge_str) else float(menge_str)
        except ValueError:
            menge = 1.0
        rest = rest[:menge_match.start()].strip()

    # Führende Positionsnummer (z.B. "1.1", "1", "3") entfernen - diese ist
    # reine Zählung und wird nicht im Artikeltext benötigt.
    posnr_pattern = r"^(\d+(?:\.\d+)?)\s+(.+)$"
    posnr_match = re.match(posnr_pattern, rest)
    if posnr_match:
        rest = posnr_match.group(2).strip()

    # Optionale führende Artikelnummer (z.B. "B-3025-078", enthält Ziffer(n)
    # und mindestens einen Bindestrich/Punkt) von der Bezeichnung trennen.
    artnr_pattern = r"^([A-Za-z0-9]+[\-./][A-Za-z0-9\-./]*\d[A-Za-z0-9\-./]*)\s+(.+)$"
    artnr_match = re.match(artnr_pattern, rest)
    artikelnummer = None
    if artnr_match:
        artikelnummer = artnr_match.group(1)
        rest = artnr_match.group(2).strip()

    artikel = rest.strip(" -")
    if not artikel:
        return None

    if artikelnummer:
        artikel = f"{artikelnummer} - {artikel}"

    return {
        "artikel": artikel,
        "menge": menge,
        "einzelpreis": einzelpreis,
        "gesamtpreis": gesamtpreis,
    }


def _to_float(value: str) -> float:
    """
    Wandelt einen Betrags-String in float um, unabhängig davon, ob er im
    deutschen Format (1.234,56 - Punkt als Tausender-, Komma als
    Dezimaltrennzeichen) oder im internationalen/englischen Format
    (1,234.56 oder 13.85 - Komma als Tausender-, Punkt als
    Dezimaltrennzeichen) vorliegt.

    Das letzte vorkommende Trennzeichen (Komma oder Punkt) wird als
    Dezimaltrennzeichen interpretiert, alle davor als Tausendertrennzeichen
    und somit entfernt.
    """
    last_comma = value.rfind(",")
    last_dot = value.rfind(".")

    if last_comma > last_dot:
        # Komma ist Dezimaltrennzeichen (deutsches Format)
        decimal_sep = ","
        thousands_sep = "."
    elif last_dot > last_comma:
        # Punkt ist Dezimaltrennzeichen (internationales Format)
        decimal_sep = "."
        thousands_sep = ","
    else:
        # Kein Trennzeichen vorhanden
        return float(value)

    cleaned = value.replace(thousands_sep, "").replace(decimal_sep, ".")
    return float(cleaned)


if __name__ == "__main__":
    sample_text = """
    Muster GmbH
    Rechnungsnummer: RE-2026-001
    Datum: 13.06.2026

    Beratungsleistung 2 50,00 100,00

    Nettobetrag: 100,00 €
    MwSt. (19%): 19,00 €
    Gesamtbetrag: 119,00 €

    IBAN: DE89 3704 0044 0532 0130 00
    """
    print(parse_invoice(sample_text))