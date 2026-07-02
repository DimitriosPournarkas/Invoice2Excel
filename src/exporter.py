"""
exporter.py

Exports extracted invoice data to Excel using pandas and openpyxl.

Supports:
- Single invoice export (backward compatible)
- Multiple invoice export (batch processing)
- In-memory export via BytesIO (no file written to disk)
"""

import io
import pandas as pd


def export_to_excel(invoice_data: dict, output_path) -> None:
    """
    Export a single invoice into an Excel file with two sheets.

    Args:
        invoice_data: Parsed invoice dictionary.
        output_path: Output .xlsx file path (str) or an in-memory
            BytesIO buffer. Passing a BytesIO buffer avoids writing
            any file to disk - useful for browser download buttons.
    """
    currency = invoice_data.get("currency", "EUR")

    kopf_data = {
        "Feld": [
            "Rechnungsnummer", "Datum", "Lieferant", "Währung",
            f"Betrag netto ({currency})", f"MwSt. ({currency})",
            f"Betrag brutto ({currency})", "IBAN",
        ],
        "Wert": [
            invoice_data.get("rechnungsnummer"), invoice_data.get("datum"),
            invoice_data.get("lieferant"), currency,
            invoice_data.get("betrag_netto"), invoice_data.get("mwst"),
            invoice_data.get("betrag_brutto"), invoice_data.get("iban"),
        ],
    }

    df_kopf = pd.DataFrame(kopf_data)
    positionen = invoice_data.get("positionen", [])

    if positionen:
        df_positionen = pd.DataFrame(positionen)
        df_positionen = df_positionen.rename(columns={
            "artikel": "Artikel", "menge": "Menge",
            "einzelpreis": f"Einzelpreis ({currency})",
            "gesamtpreis": f"Gesamtpreis ({currency})",
        })
    else:
        df_positionen = pd.DataFrame(columns=[
            "Artikel", "Menge",
            f"Einzelpreis ({currency})", f"Gesamtpreis ({currency})",
        ])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_kopf.to_excel(writer, sheet_name="Rechnung", index=False)
        df_positionen.to_excel(writer, sheet_name="Positionen", index=False)


def export_multiple_to_excel(invoices: list[dict], output_path) -> None:
    """
    Export multiple invoices into a single Excel workbook.

    Args:
        invoices: List of parsed invoice dictionaries.
        output_path: Output .xlsx file path (str) or BytesIO buffer.
    """
    invoice_rows = []
    position_rows = []

    for inv in invoices:
        currency = inv.get("currency", "EUR")
        source_file = inv.get("source_file")

        invoice_rows.append({
            "source_file": source_file,
            "rechnungsnummer": inv.get("rechnungsnummer"),
            "datum": inv.get("datum"),
            "lieferant": inv.get("lieferant"),
            "currency": currency,
            "betrag_netto": inv.get("betrag_netto"),
            "mwst": inv.get("mwst"),
            "betrag_brutto": inv.get("betrag_brutto"),
            "iban": inv.get("iban"),
        })

        for pos in inv.get("positionen", []):
            position_rows.append({
                "source_file": source_file,
                "rechnungsnummer": inv.get("rechnungsnummer"),
                "artikel": pos.get("artikel"),
                "menge": pos.get("menge"),
                "einzelpreis": pos.get("einzelpreis"),
                "gesamtpreis": pos.get("gesamtpreis"),
                "currency": currency,
            })

    df_invoices = pd.DataFrame(invoice_rows)
    df_positions = pd.DataFrame(position_rows) if position_rows else pd.DataFrame(
        columns=["source_file", "rechnungsnummer", "artikel", "menge",
                 "einzelpreis", "gesamtpreis", "currency"]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_invoices.to_excel(writer, sheet_name="Rechnungen", index=False)
        df_positions.to_excel(writer, sheet_name="Positionen", index=False)


if __name__ == "__main__":
    example = {
        "rechnungsnummer": "RE-2026-001",
        "datum": "13.06.2026",
        "lieferant": "Muster GmbH",
        "betrag_netto": 100.00,
        "mwst": 19.00,
        "betrag_brutto": 119.00,
        "currency": "EUR",
        "iban": "DE89370400440532013000",
        "positionen": [{"artikel": "Beratung", "menge": 2, "einzelpreis": 50.0, "gesamtpreis": 100.0}],
    }
    export_to_excel(example, "test_output.xlsx")
    print("Excel-Datei erstellt: test_output.xlsx")

    buf = io.BytesIO()
    export_to_excel(example, buf)
    print(f"In-Memory Export: {buf.tell()} Bytes")