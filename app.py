"""
Invoice2Excel - Streamlit main application
Uploads a PDF invoice, extracts structured data and exports it to Excel
(optionally also storing it in a SQLite database).
"""

import streamlit as st
import tempfile
import os
from pathlib import Path

from src.extractor import extract_text_from_pdf
from src.parser import parse_invoice
from src.exporter import export_to_excel
from src.database import save_invoice_to_db, get_all_invoices

st.set_page_config(page_title="Invoice2Excel", page_icon="🧾")

st.title("🧾 Invoice2Excel")
st.write("PDF-Rechnung hochladen, Daten automatisch extrahieren und als Excel exportieren.")

uploaded_file = st.file_uploader("PDF-Rechnung auswählen", type=["pdf"])

save_db = st.checkbox("In Datenbank speichern", value=False)

if uploaded_file is not None:
    # Save to a temporary file, since pdfplumber requires a file path
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        text = extract_text_from_pdf(tmp_path)
        invoice_data = parse_invoice(text)

        st.subheader("Erkannte Rechnungsdaten")
        st.json(invoice_data)

        # Use the uploaded PDF's filename for the Excel output
        # (e.g. "Rechnung1.pdf" -> "Rechnung1.xlsx")
        pdf_stem = Path(uploaded_file.name).stem
        output_path = Path("output") / f"{pdf_stem}.xlsx"
        output_path.parent.mkdir(exist_ok=True)
        export_to_excel(invoice_data, str(output_path))

        if save_db:
            # Save to the database only once per uploaded file, even if
            # Streamlit reruns this script (e.g. when toggling checkboxes).
            db_key = f"saved_to_db::{uploaded_file.file_id}"
            if not st.session_state.get(db_key):
                save_invoice_to_db(invoice_data)
                st.session_state[db_key] = True
            st.success("Excel exportiert und in Datenbank gespeichert ✅")
        else:
            st.success("Excel exportiert ✅")

        with open(output_path, "rb") as f:
            st.download_button(
                label="Excel-Datei herunterladen",
                data=f,
                file_name=output_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    finally:
        os.unlink(tmp_path)

# Optional section: show invoices previously saved to the database
with st.expander("📊 Gespeicherte Rechnungen (Datenbank)"):
    invoices = get_all_invoices()
    if invoices:
        st.dataframe(invoices)
    else:
        st.write("Noch keine Rechnungen in der Datenbank gespeichert.")