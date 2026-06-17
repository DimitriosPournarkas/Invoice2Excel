"""
parser.py
Detects structured fields from raw invoice text using regular expressions:
invoice number, date, vendor, amounts, IBAN, and invoice line items.
"""

import re
from datetime import datetime

# Amount in German format (1.234,56 / 1234,56) OR international format
# (1,234.56 / 1234.56 / 13.85). Group 1 captures the full numeric string
# including separators. Decimal part allows 2-4 digits to also cover
# sub-cent precision used in some usage-based/subscription invoices
# (e.g. "3,3529 EUR" for a pro-rated monthly price).
AMOUNT = r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2,4}|\d+[.,]\d{2,4})"

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
    Extracts structured invoice data from raw text.

    Args:
        text: The raw text obtained from extractor.extract_text_from_pdf().

    Returns:
        A dictionary with the recognized fields. Fields that could not be
        found contain None. Note: the dictionary keys themselves stay in
        German (rechnungsnummer, datum, lieferant, ...) to keep the
        existing data contract used by the rest of the project intact.
    """
    amounts = _extract_amounts(text)
    return {
        "rechnungsnummer": _extract_invoice_number(text),
        "datum": _extract_date(text),
        "lieferant": _extract_vendor(text),
        "betrag_netto": amounts["net"],
        "mwst": amounts["vat"],
        "betrag_brutto": amounts["gross"],
        "currency": _extract_currency(text),
        "iban": _extract_iban(text),
        "positionen": _extract_line_items(text),
    }


def _extract_invoice_number(text: str) -> str | None:
    """Extracts the invoice number (e.g. 'RE-2026-001')."""
    pattern = (
        r"(?:Rechnungs?\s*-?\s*(?:Nr\.?|nummer)|Rechnung|Invoice\s*(?:No\.?|Number)|Beleg\s*(?:-?Nr\.?|nummer)?)"
        r"[:\s]*([A-Za-z0-9][A-Za-z0-9\-/]*\d[A-Za-z0-9\-/]*)"
    )
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_date(text: str) -> str | None:
    """
    Extracts the invoice date with the following priority:
    1. Explicitly labeled as invoice date ("Rechnungsdatum"/"Datum")
    2. A plausible date found in the header area of the invoice
    3. The first plausible date found anywhere in the text
    4. Fallback: the first syntactically valid date, even without context
    """

    # 1. Explicit label
    labeled_match = re.search(
        r"(?:Rechnungs?datum|Datum)[:\s]*(\d{1,2}\.\d{1,2}\.\d{2,4})",
        text,
        re.IGNORECASE,
    )
    if labeled_match:
        date_str = labeled_match.group(1)
        if _is_valid_date(date_str):
            return date_str

    # 2. Header area (first 15 lines)
    header_lines = text.splitlines()[:15]
    for line in header_lines:
        for date_str in re.findall(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", line):
            if _is_valid_date(date_str) and _is_likely_invoice_date(date_str, text):
                return date_str

    # 3. Anywhere in the text, preferring dates near invoice-related keywords
    all_dates = re.findall(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", text)
    for date_str in all_dates:
        if _is_valid_date(date_str) and _is_likely_invoice_date(date_str, text):
            return date_str

    # 4. Fallback: first syntactically valid date, regardless of context
    for date_str in all_dates:
        if _is_valid_date(date_str):
            return date_str

    return None


def _is_valid_date(date_str: str) -> bool:
    """Checks whether the string is a real calendar date (rejects e.g. 32.13.2026)."""
    try:
        day, month, year = (int(part) for part in date_str.split("."))
        datetime(year, month, day)
        return True
    except (ValueError, TypeError):
        return False


def _is_likely_invoice_date(date_str: str, text: str) -> bool:
    """
    Checks whether a date is plausibly the invoice date:
    - Falls within a reasonable year range (not absurdly old or far in the future)
    - Appears near a keyword such as "Rechnung" or "Datum" in the surrounding text

    Note: this only inspects the context around the FIRST occurrence of
    date_str in the text. If the same date string occurs multiple times
    (e.g. invoice date and due date happen to match), only that first
    occurrence is checked.
    """
    day, month, year = (int(part) for part in date_str.split("."))

    # Reject implausible years (window grows with the current year so this
    # doesn't need to be updated manually every few years)
    current_year = datetime.now().year
    if year < 2000 or year > current_year + 2:
        return False

    # Check context: does "Rechnung"/"Datum" appear nearby?
    date_pos = text.find(date_str)
    context = text[max(0, date_pos - 50):min(len(text), date_pos + 50)]
    return bool(re.search(r"(Rechnung|Rechnungsdatum|Datum)", context, re.IGNORECASE))


def _extract_vendor(text: str) -> str | None:
    """
    Heuristic: the company name is often found together with a legal
    form suffix (GmbH, AG, e.K., etc.) in one of the first few lines.
    """
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


def _extract_amounts(text: str) -> dict:
    """
    Extracts the net, VAT, and gross amounts.

    Tries the simple inline "label: amount" pattern first (covers most
    invoices, where e.g. "Nettobetrag: 100,00 €" appears as one phrase).
    For any field that isn't found this way, falls back to detecting a
    summary table layout - common for usage-based or subscription
    invoices, where column headers like "Nettorechnungs-Betrag" /
    "USt-Betrag" / "Bruttorechnungs-Betrag" appear in one line and the
    actual amounts appear in a data row (often a "Summe" row) below it.
    """
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
    """
    Searches for monetary amounts (German or international number format,
    e.g. 1.234,56 € or 1234.56) for the categories 'net', 'vat' (German
    "MwSt"/"USt") and 'gross'. The currency symbol may appear before or
    after the amount. This only matches when the label and the amount sit
    right next to each other on the same line.
    """
    keywords = {
        "net": r"(?:Netto(?:betrag)?|Zwischensumme|Summe\s+Netto)",
        "vat": r"(?:MwSt\.?|USt\.?|Umsatzsteuer)(?:\s*\(?\d{1,2}(?:[.,]\d{1,2})?\s*%\)?)?(?:\s+auf\s+[\d.,]+\s*€?)?",
        "gross": r"(?:Brutto(?:betrag)?|Gesamtbetrag|Gesamt(?:summe)?|Rechnungsbetrag|Endbetrag|End-?summe)",
    }

    # Amount with an optional currency symbol/code before or after it
    amount_pattern = rf"(?:{CURRENCY_SYMBOL}\s*)?{AMOUNT}\s*{CURRENCY_SYMBOL}?"
    pattern = rf"{keywords[kind]}[:\s]*{amount_pattern}"

    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None

    return _to_float(match.group(1))


def _extract_amounts_from_summary_table(text: str) -> dict:
    """
    Detects a net/VAT/gross summary table and reads the amounts from it.

    Looks for a header line that contains at least two of the column
    labels "Netto...Betrag", "MwSt/USt...Betrag", and "Brutto...Betrag"
    (requiring the "Betrag" suffix avoids false positives like a
    "USt-Satz" rate column, which has no matching amount column). The
    left-to-right order of the labels found in that line determines
    which amount belongs to which category.

    Once the header is found, the amounts are read from the nearest
    "Summe" row below it (the authoritative total), or - if no such row
    exists - the first row below the header that has at least as many
    amounts as labels were found.
    """
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

    # Look a few lines below the header for the actual values, preferring
    # a "Summe" row over a plain data row.
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

    # Use the last len(order) amounts on the line, in case the row also
    # contains a leading value without decimals (e.g. a tax rate like
    # "19 %", which won't match AMOUNT anyway and is excluded already).
    relevant_amounts = amounts[-len(order):]

    return {kind: _to_float(amount) for kind, amount in zip(order, relevant_amounts)}


def _extract_iban(text: str) -> str | None:
    """Extracts the IBAN, preferring an explicit "IBAN:" label over a bare pattern match."""
    # Explicitly look for "IBAN" followed by an IBAN-like pattern (country
    # code + check digits + up to 30 alphanumeric characters, possibly
    # grouped by spaces).
    pattern = r"IBAN[:\s]*([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{1,4}){2,9})"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        iban = match.group(1).replace(" ", "")
        return iban.upper()

    # Fallback: IBAN-like pattern without keyword
    pattern = r"\b([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}\s?[A-Z0-9]{0,3})\b"
    match = re.search(pattern, text)
    if match:
        return match.group(1).replace(" ", "")
    return None


def _extract_line_items(text: str) -> list[dict]:
    """
    Detects invoice line items by first delimiting the table area using
    keywords:

    - Table start: a line that looks like a table header row (contains
      e.g. "Bezeichnung"/"Artikel"/"Beschreibung" AND "Menge"/"Anzahl"
      AND "Preis"/"Gesamt").
    - Table end: the first line after that which starts with a total/sum
      keyword ("Summe", "Zwischensumme", "Gesamt", "Endsumme", ...).

    Within this area, each line is interpreted generically (column-based):
    the last two monetary amounts in the line are unit price and total
    price, a value with an optional unit before them is the quantity, and
    the remainder of the line (possibly after a leading position/article
    number) is the item description.

    This approach is intentionally layout-independent so that new invoice
    formats are covered without adding extra fixed line patterns. For
    very unusual layouts (e.g. multi-line table cells) it may still be
    necessary to use extract_tables_from_pdf() as a supplement.
    """
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
                or re.match(vat_rate_breakdown_row, line)):
            continue
        item = _parse_line_item(line)
        if item:
            line_items.append(item)

    return line_items


def _find_table_start(lines: list[str]) -> int | None:
    """
    Finds the line that looks like a table header row.

    Normally requires a description-type column AND a quantity-type
    column alongside a price column. Some invoices (e.g. usage-based or
    subscription billing) instead have a "Zeitraum" (period) column with
    no explicit quantity, in which case the price column alone next to
    "Zeitraum" is treated as a valid header.
    """
    description_keywords = r"(?:Bezeichnung|Artikel|Beschreibung|Leistung|Position)"
    quantity_keywords = r"(?:Menge|Anzahl|Stück)"
    price_keywords = r"(?:Preis|Gesamt|Betrag|Summe)"
    period_keywords = r"Zeitraum"

    for i, line in enumerate(lines):
        if not re.search(price_keywords, line, re.IGNORECASE):
            continue
        has_description = re.search(description_keywords, line, re.IGNORECASE)
        has_quantity = re.search(quantity_keywords, line, re.IGNORECASE)
        has_period = re.search(period_keywords, line, re.IGNORECASE)
        if (has_description and has_quantity) or has_period:
            return i

    return None


def _find_table_end(lines: list[str], start: int) -> int:
    """
    Finds the first line from `start` onward that marks the end of the table.

    A line starting with "Summe"/"Zwischensumme"/... marks the table end -
    UNLESS it is a category-level subtotal (e.g. "Summe Material: 1.224,90 €")
    that is directly followed by a new category heading (e.g. "2. Arbeit").
    In that case, the table continues.

    If no final total line is found, the end of the list is returned.
    """
    end_keywords = (
        r"^(?:Summe|Zwischensumme|Gesamt(?:summe)?|Endsumme|Netto(?:betrag)?|"
        r"Brutto(?:betrag)?|Rechnungsbetrag)\b"
    )
    category_heading = r"^\d+\.\s+[A-Za-zÄÖÜäöüß]+$"

    for i in range(start, len(lines)):
        if re.match(end_keywords, lines[i], re.IGNORECASE):
            # Check whether a new category heading directly follows
            # (= this "Summe" line was just a subtotal)
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if re.match(category_heading, next_line):
                continue
            return i

    return len(lines)


def _parse_line_item(line: str) -> dict | None:
    """
    Parses a single table row column-based:

    - Finds all monetary amounts in German format (e.g. 1.234,56) in the line.
    - The last two of them are interpreted as unit price and total price
      (if only one amount is present: it is used as the total price, with
      quantity = 1).
    - Before these amounts, a quantity value is searched for (a number,
      optionally followed by a unit such as "Stk."/"Std."/"Eimer").
    - The remaining text before that (possibly after a leading position/
      article number) is the item description.

    Returns None if the line does not look like a line item (e.g. no
    monetary amount present, or no item description remains).
    """
    # Some invoices prefix the row with a billing period (e.g.
    # "01.05.26-31.05.26Paketpreis ...", often glued directly to the
    # description due to PDF text extraction). Detect and strip that
    # period upfront so it doesn't end up mixed into the description.
    period_match = re.match(
        r"^(\d{1,2}\.\d{1,2}\.\d{2,4})\s*-\s*(\d{1,2}\.\d{1,2}\.\d{2,4})", line
    )
    period = None
    if period_match:
        period = f"{period_match.group(1)}-{period_match.group(2)}"
        line = line[period_match.end():]

    amounts = list(re.finditer(rf"{CURRENCY_SYMBOL}?\s*{AMOUNT}\s*{CURRENCY_SYMBOL}?", line, re.IGNORECASE))

    if not amounts:
        return None

    # Last two amounts = unit price and total price (or just total price)
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

    # Search for a quantity (with optional unit) at the end of the remaining text
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

    # Remove a leading position number (e.g. "1.1", "1", "3") - this is
    # just a counter and not needed in the item text.
    pos_number_pattern = r"^(\d+(?:\.\d+)?)\s+(.+)$"
    pos_number_match = re.match(pos_number_pattern, remainder)
    if pos_number_match:
        remainder = pos_number_match.group(2).strip()

    # Optional leading article number (e.g. "B-3025-078", contains digit(s)
    # and at least one hyphen/dot), separated from the description.
    item_number_pattern = r"^([A-Za-z0-9]+[\-./][A-Za-z0-9\-./]*\d[A-Za-z0-9\-./]*)\s+(.+)$"
    item_number_match = re.match(item_number_pattern, remainder)
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
    """
    Converts an amount string to float, regardless of whether it is in
    German format (1.234,56 - dot as thousands separator, comma as
    decimal separator) or international/English format (1,234.56 or
    13.85 - comma as thousands separator, dot as decimal separator).

    The last separator (comma or dot) encountered is treated as the
    decimal separator; everything before it is treated as a thousands
    separator and removed accordingly.
    """
    last_comma = value.rfind(",")
    last_dot = value.rfind(".")

    if last_comma > last_dot:
        # Comma is the decimal separator (German format)
        decimal_sep = ","
        thousands_sep = "."
    elif last_dot > last_comma:
        # Dot is the decimal separator (international format)
        decimal_sep = "."
        thousands_sep = ","
    else:
        # No separator present
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