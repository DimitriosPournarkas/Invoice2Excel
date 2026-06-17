"""
Invoice2Excel - Streamlit main application
Uploads one or more PDF invoices, extracts structured data and exports it
to Excel (optionally also storing it in a SQLite database).
"""

import streamlit as st
import tempfile
import os
from pathlib import Path

from src.extractor import extract_text_from_pdf
from src.parser import parse_invoice
from src.exporter import export_to_excel, export_multiple_to_excel
from src.database import save_invoice_to_db, get_all_invoices

st.set_page_config(page_title="Invoice2Excel", page_icon="🧾")

st.title("🧾 Invoice2Excel")
st.write("PDF-Rechnung(en) hochladen, Daten automatisch extrahieren und als Excel exportieren.")

uploaded_files = st.file_uploader(
    "PDF-Rechnung(en) auswählen", type=["pdf"], accept_multiple_files=True
)

save_db = st.checkbox("In Datenbank speichern", value=False)

combine_files = False
if uploaded_files and len(uploaded_files) > 1:
    combine_files = st.checkbox(
        "Alle Rechnungen in eine Excel-Datei zusammenfassen", value=False
    )


def _process_pdf(uploaded_file) -> dict:
    """Extracts text from an uploaded PDF and parses it into invoice data."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        text = extract_text_from_pdf(tmp_path)
        return parse_invoice(text)
    finally:
        os.unlink(tmp_path)


def _save_to_db_once(uploaded_file, invoice_data: dict) -> None:
    """Saves an invoice to the database only once per uploaded file, even
    if Streamlit reruns this script (e.g. when toggling checkboxes)."""
    db_key = f"saved_to_db::{uploaded_file.file_id}"
    if not st.session_state.get(db_key):
        save_invoice_to_db(invoice_data)
        st.session_state[db_key] = True


if uploaded_files:
    Path("output").mkdir(exist_ok=True)

    if len(uploaded_files) == 1 or not combine_files:
        # Single file, or multiple files processed individually
        for uploaded_file in uploaded_files:
            invoice_data = _process_pdf(uploaded_file)

            st.subheader(f"Erkannte Rechnungsdaten: {uploaded_file.name}")
            st.json(invoice_data)

            # Use the uploaded PDF's filename for the Excel output
            # (e.g. "Rechnung1.pdf" -> "Rechnung1.xlsx")
            pdf_stem = Path(uploaded_file.name).stem
            output_path = Path("output") / f"{pdf_stem}.xlsx"
            export_to_excel(invoice_data, str(output_path))

            if save_db:
                _save_to_db_once(uploaded_file, invoice_data)
                st.success("Excel exportiert und in Datenbank gespeichert ✅")
            else:
                st.success("Excel exportiert ✅")

            with open(output_path, "rb") as f:
                st.download_button(
                    label=f"Excel-Datei herunterladen ({output_path.name})",
                    data=f,
                    file_name=output_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download::{uploaded_file.file_id}",
                )

    else:
        # Multiple files combined into a single Excel file
        invoices_data = []
        for uploaded_file in uploaded_files:
            invoice_data = _process_pdf(uploaded_file)
            invoice_data["source_file"] = uploaded_file.name
            invoices_data.append(invoice_data)

            st.subheader(f"Erkannte Rechnungsdaten: {uploaded_file.name}")
            st.json(invoice_data)

            if save_db:
                _save_to_db_once(uploaded_file, invoice_data)

        output_path = Path("output") / "Rechnungen_Sammelexport.xlsx"
        export_multiple_to_excel(invoices_data, str(output_path))

        if save_db:
            st.success("Excel exportiert und in Datenbank gespeichert ✅")
        else:
            st.success("Excel exportiert ✅")

        with open(output_path, "rb") as f:
            st.download_button(
                label=f"Excel-Datei herunterladen ({output_path.name})",
                data=f,
                file_name=output_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

# Optional section: show invoices previously saved to the database
with st.expander("📊 Gespeicherte Rechnungen (Datenbank)"):
    invoices = get_all_invoices()
    if invoices:
        st.dataframe(invoices)
    else:
        st.write("Noch keine Rechnungen in der Datenbank gespeichert.")