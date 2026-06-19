"""
parser.py
Detects structured fields from raw invoice text using regular expressions:
invoice number, date, vendor, amounts, IBAN, and invoice line items.
"""

import re
from datetime import datetime

AMOUNT = r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2,4}|\d+[.,]\d{2,4})"
CURRENCY_SYMBOL = r"(?:€|\$|£|CHF|EUR|USD|GBP|Fr\.)"

_CURRENCY_MAP = {
    "€": "EUR", "EUR": "EUR", "$": "USD", "USD": "USD",
    "£": "GBP", "GBP": "GBP", "CHF": "CHF", "FR.": "CHF",
}

# Lines that start with these patterns are footer/note text, not line items.
_JUNK_LINE_PATTERNS = re.compile(
    r"^(?:"
    r"Dieser|Diese|Bitte|Hinweis|Es\s+gelten|Gemäß|Entspricht|"
    r"Enthält|Inklusive|inkl\.\s|zzgl\.|zuzüglich|"
    r"Alle\s+Preise|Preise\s+sind|"
    r"Bei\s+Fragen|Für\s+Rückfragen|"
    r"Zahlung|Zahlbar|Fällig|"
    r"Steuer(?:nummer|Nr)|USt\.?-?Id|"
    r"Vielen\s+Dank|Danke|"
    r"Mit\s+freundlichen|Freundliche\s+Grüße|"
    r"Seite\s+\d|Page\s+\d"
    r")",
    re.IGNORECASE,
)

# Minimum description length – shorter strings are likely noise.
_MIN_DESCRIPTION_LENGTH = 3


def parse_invoice(text: str) -> dict:
    amounts = _extract_amounts(text)
    positionen = _extract_line_items(text)

    # Fallback: Beträge aus Positionen berechnen wenn der Parser in der
    # Summenzeile nichts gefunden hat (typisch bei gescannten Rechnungen).
    # Annahme: Positionssumme = Netto, MwSt = 19%, Brutto = Netto × 1.19.
    # Der User kann alle drei Werte danach im Browser korrigieren.
    if positionen and not amounts.get("gross"):
        gesamt = round(sum(p.get("gesamtpreis") or 0 for p in positionen), 2)
        if gesamt > 0:
            amounts["net"] = amounts.get("net") or gesamt
            if not amounts.get("vat"):
                amounts["vat"] = round(gesamt * 0.19, 2)
            if not amounts.get("gross"):
                amounts["gross"] = round(gesamt + amounts["vat"], 2)

    return {
        "rechnungsnummer": _extract_invoice_number(text) or "",
        "datum": _extract_date(text) or "",
        "lieferant": _extract_vendor(text) or "",
        "betrag_netto": amounts["net"],
        "mwst": amounts["vat"],
        "betrag_brutto": amounts["gross"],
        "currency": _extract_currency(text),
        "iban": _extract_iban(text) or "",
        "positionen": positionen,
    }


def _extract_invoice_number(text: str) -> str | None:
    pattern = (
        r"(?:Rechnungs?\s*-?\s*(?:Nr\.?|nummer)|Rechnung|Invoice\s*(?:No\.?|Number)|Beleg\s*(?:-?Nr\.?|nummer)?)"
        r"[:\s]*([A-Za-z0-9][A-Za-z0-9\-/]*\d[A-Za-z0-9\-/]*)"
    )
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_date(text: str) -> str | None:
    labeled_match = re.search(
        r"(?:Rechnungs?datum|Datum)[:\s]*(\d{1,2}\.\d{1,2}\.\d{2,4})",
        text, re.IGNORECASE,
    )
    if labeled_match:
        date_str = labeled_match.group(1)
        if _is_valid_date(date_str):
            return date_str

    header_lines = text.splitlines()[:15]
    for line in header_lines:
        for date_str in re.findall(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", line):
            if _is_valid_date(date_str) and _is_likely_invoice_date(date_str, text):
                return date_str

    all_dates = re.findall(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", text)
    for date_str in all_dates:
        if _is_valid_date(date_str) and _is_likely_invoice_date(date_str, text):
            return date_str

    for date_str in all_dates:
        if _is_valid_date(date_str):
            return date_str

    return None


def _is_valid_date(date_str: str) -> bool:
    try:
        day, month, year = (int(part) for part in date_str.split("."))
        datetime(year, month, day)
        return True
    except (ValueError, TypeError):
        return False


def _is_likely_invoice_date(date_str: str, text: str) -> bool:
    day, month, year = (int(part) for part in date_str.split("."))
    current_year = datetime.now().year
    if year < 2000 or year > current_year + 2:
        return False
    date_pos = text.find(date_str)
    context = text[max(0, date_pos - 50):min(len(text), date_pos + 50)]
    return bool(re.search(r"(Rechnung|Rechnungsdatum|Datum)", context, re.IGNORECASE))


def _extract_vendor(text: str) -> str | None:
    pattern = r"^(.*?(?:GmbH|AG|KG|e\.K\.|UG|OHG|GbR))\b"
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_currency(text: str) -> str:
    matches = re.findall(CURRENCY_SYMBOL, text, re.IGNORECASE)
    if not matches:
        return "EUR"
    counts: dict[str, int] = {}
    for match in matches:
        code = _CURRENCY_MAP.get(match.upper(), _CURRENCY_MAP.get(match, "EUR"))
        counts[code] = counts.get(code, 0) + 1
    return max(counts, key=counts.get)


def _extract_amounts(text: str) -> dict:
    result = {
        "net": _extract_inline_amount(text, "net"),
        "vat": _extract_inline_amount(text, "vat"),
        "gross": _extract_inline_amount(text, "gross"),
    }
    if any(value is None for value in result.values()):
        table_amounts = _extract_amounts_from_summary_table(text)
        for kind, value in table_amounts.items():
            if result.get(kind) is None and value is not None:
                result[kind] = value
    return result


def _extract_inline_amount(text: str, kind: str) -> float | None:
    keywords = {
        "net": r"(?:Netto(?:betrag)?|Zwischensumme|Summe\s+Netto)",
        "vat": r"(?:MwSt\.?|USt\.?|Umsatzsteuer)(?:\s*\(?\d{1,2}(?:[.,]\d{1,2})?\s*%\)?)?(?:\s+auf\s+[\d.,]+\s*€?)?",
        "gross": r"(?:Brutto(?:betrag)?|Gesamtbetrag|Gesamt(?:summe)?|Rechnungsbetrag|Endbetrag|End-?summe)",
    }
    amount_pattern = rf"(?:{CURRENCY_SYMBOL}\s*)?{AMOUNT}\s*{CURRENCY_SYMBOL}?"
    pattern = rf"{keywords[kind]}[:\s]*{amount_pattern}"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return _to_float(match.group(1))


def _extract_amounts_from_summary_table(text: str) -> dict:
    lines = text.splitlines()
    label_patterns = {
        "net": r"Netto[\w-]*?Betrag",
        "vat": r"(?:MwSt|USt|Umsatzsteuer)[\w-]*?Betrag",
        "gross": r"Brutto[\w-]*?Betrag",
    }
    header_idx = None
    order: list[str] = []
    for i, line in enumerate(lines):
        found = []
        for kind, pattern in label_patterns.items():
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                found.append((match.start(), kind))
        if len(found) >= 2:
            found.sort()
            header_idx = i
            order = [kind for _, kind in found]
            break

    if header_idx is None:
        return {}

    candidate_lines = lines[header_idx + 1:header_idx + 6]
    data_line = next(
        (line for line in candidate_lines if re.match(r"^\s*Summe\b", line, re.IGNORECASE)),
        None,
    )
    if data_line is None:
        for line in candidate_lines:
            if len(re.findall(AMOUNT, line)) >= len(order):
                data_line = line
                break

    if data_line is None:
        return {}

    amounts = re.findall(AMOUNT, data_line)
    if len(amounts) < len(order):
        return {}

    relevant_amounts = amounts[-len(order):]
    return {kind: _to_float(amount) for kind, amount in zip(order, relevant_amounts)}


def _extract_iban(text: str) -> str | None:
    pattern = r"IBAN[:\s]*([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{1,4}){2,9})"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).replace(" ", "").upper()
    pattern = r"\b([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}\s?[A-Z0-9]{0,3})\b"
    match = re.search(pattern, text)
    if match:
        return match.group(1).replace(" ", "")
    return None


def _extract_line_items(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines()]
    start_idx = _find_table_start(lines)
    if start_idx is None:
        return []

    end_idx = _find_table_end(lines, start_idx + 1)

    line_items = []
    category_heading = r"^\d+\.\s+[A-Za-zÄÖÜäöüß]+$"
    subtotal = r"^(?:Summe|Zwischensumme)\b"
    vat_rate_breakdown_row = r"^\d{1,3}(?:[.,]\d{1,2})?\s*%"

    for line in lines[start_idx + 1:end_idx]:
        if not line:
            continue
        if (re.match(category_heading, line)
                or re.match(subtotal, line, re.IGNORECASE)
                or re.match(vat_rate_breakdown_row, line)
                or _JUNK_LINE_PATTERNS.match(line)):
            continue
        item = _parse_line_item(line)
        if item and len(item.get("artikel", "")) >= _MIN_DESCRIPTION_LENGTH:
            line_items.append(item)

    return line_items


def _find_table_start(lines: list[str]) -> int | None:
    description_keywords = r"(?:Bezeichnung|Artikel|Beschreibung|Leistung|Position)"
    quantity_keywords = r"(?:Menge|Anzahl|Stück)"
    price_keywords = r"(?:Preis|Gesamt|Betrag|Summe)"
    period_keywords = r"Zeitraum"

    for i, line in enumerate(lines):
        if not re.search(price_keywords, line, re.IGNORECASE):
            continue
        if (re.search(description_keywords, line, re.IGNORECASE)
                or re.search(quantity_keywords, line, re.IGNORECASE)
                or re.search(period_keywords, line, re.IGNORECASE)):
            return i
    return None


def _find_table_end(lines: list[str], start: int) -> int:
    end_keywords = (
        r"^(?:Summe|Zwischensumme|Gesamt(?:summe)?|Endsumme|Netto(?:betrag)?|"
        r"Brutto(?:betrag)?|Rechnungsbetrag)\b"
    )
    category_heading = r"^\d+\.\s+[A-Za-zÄÖÜäöüß]+$"

    for i in range(start, len(lines)):
        if re.match(end_keywords, lines[i], re.IGNORECASE):
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if re.match(category_heading, next_line):
                continue
            return i
    return len(lines)


def _parse_line_item(line: str) -> dict | None:
    period_match = re.search(
        r"(\d{1,2}\.\d{1,2}\.\d{2,4})\s*-\s*(\d{1,2}\.\d{1,2}\.\d{2,4})", line
    )
    period = None
    if period_match:
        period = f"{period_match.group(1)}-{period_match.group(2)}"
        line = line[:period_match.start()] + " " + line[period_match.end():]

    amounts = list(re.finditer(rf"{CURRENCY_SYMBOL}?\s*{AMOUNT}\s*{CURRENCY_SYMBOL}?", line, re.IGNORECASE))

    if not amounts:
        return None

    if len(amounts) >= 2:
        unit_price_match, total_price_match = amounts[-2], amounts[-1]
        unit_price = _to_float(unit_price_match.group(1))
        total_price = _to_float(total_price_match.group(1))
        remainder_end = unit_price_match.start()
    else:
        total_price_match = amounts[-1]
        total_price = _to_float(total_price_match.group(1))
        unit_price = total_price
        remainder_end = total_price_match.start()

    remainder = line[:remainder_end].strip()

    quantity = 1.0
    quantity_pattern = rf"({AMOUNT}|\d+)\s*(?:[A-Za-zÄÖÜäöüß]+\.?)?\s*$"
    quantity_match = re.search(quantity_pattern, remainder)
    if quantity_match:
        quantity_str = quantity_match.group(1)
        try:
            quantity = _to_float(quantity_str) if ("," in quantity_str or "." in quantity_str) else float(quantity_str)
        except ValueError:
            quantity = 1.0
        remainder = remainder[:quantity_match.start()].strip()

    pos_number_match = re.match(r"^(\d+(?:\.\d+)?)\s+(.+)$", remainder)
    if pos_number_match:
        remainder = pos_number_match.group(2).strip()

    item_number_match = re.match(
        r"^([A-Za-z0-9]+[\-./][A-Za-z0-9\-./]*\d[A-Za-z0-9\-./]*)\s+(.+)$", remainder
    )
    item_number = None
    if item_number_match:
        item_number = item_number_match.group(1)
        remainder = item_number_match.group(2).strip()

    description = remainder.strip(" -")
    if not description:
        return None

    if item_number:
        description = f"{item_number} - {description}"

    result = {
        "artikel": description,
        "menge": quantity,
        "einzelpreis": unit_price,
        "gesamtpreis": total_price,
    }
    if period:
        result["zeitraum"] = period

    return result


def _to_float(value: str) -> float:
    last_comma = value.rfind(",")
    last_dot = value.rfind(".")
    if last_comma > last_dot:
        decimal_sep, thousands_sep = ",", "."
    elif last_dot > last_comma:
        decimal_sep, thousands_sep = ".", ","
    else:
        return float(value)
    return float(value.replace(thousands_sep, "").replace(decimal_sep, "."))


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