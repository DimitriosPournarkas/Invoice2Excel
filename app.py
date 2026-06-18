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
from src.database import save_invoice_to_db, get_all_invoices, save_correction
from src.categorizer import suggest_category, get_categories

st.set_page_config(page_title="Invoice2Excel", page_icon="🧾")

st.title("🧾 Invoice2Excel")
st.write("PDF-Rechnung(en) hochladen, Daten automatisch extrahieren und als Excel exportieren.")

uploaded_files = st.file_uploader(
    "PDF-Rechnung(en) auswählen", type=["pdf"], accept_multiple_files=True
)

combine_files = False
if uploaded_files and len(uploaded_files) > 1:
    combine_files = st.checkbox(
        "Alle Rechnungen in eine Excel-Datei zusammenfassen", value=False
    )

CATEGORY_OPTIONS = get_categories()


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


# Bekannte Felder in sinnvoller Reihenfolge mit Anzeige-Label. Felder, die
# der Parser zusätzlich liefert (z.B. eine Adresse) und die hier nicht
# gelistet sind, werden trotzdem automatisch editierbar gemacht.
FIELD_LABELS = {
    "rechnungsnummer": "Rechnungsnummer",
    "datum": "Datum (TT.MM.JJJJ)",
    "lieferant": "Lieferant / Name",
    "adresse": "Adresse",
    "iban": "IBAN",
    "betrag_netto": "Betrag netto",
    "mwst": "MwSt.",
    "betrag_brutto": "Betrag brutto",
}
NUMBER_FIELDS = {"betrag_netto", "mwst", "betrag_brutto"}
EXCLUDED_FIELDS = {"category", "tags", "source_file"}


def _editable_invoice_form(invoice_data: dict, widget_key: str) -> dict:
    """Shows editable inputs for every scalar field the parser extracted, so
    the user can correct anything that was read wrong - falsches Datum,
    falscher Name/Lieferant, falsche Adresse, falsche Beträge, etc.

    Works generically: any scalar key present in invoice_data gets an input
    field automatically, even ones not explicitly listed in FIELD_LABELS, so
    future parser fields are editable without changing this code.
    """
    updated = dict(invoice_data)

    scalar_keys = [
        key for key, value in invoice_data.items()
        if key != "positionen"
        and key not in EXCLUDED_FIELDS
        and not isinstance(value, (list, dict))
    ]
    # Bekannte Felder zuerst in der Reihenfolge oben, unbekannte danach.
    ordered_keys = [k for k in FIELD_LABELS if k in scalar_keys]
    ordered_keys += [k for k in scalar_keys if k not in ordered_keys]

    cols = st.columns(2)
    for i, key in enumerate(ordered_keys):
        label = FIELD_LABELS.get(key, key.replace("_", " ").capitalize())
        with cols[i % 2]:
            if key in NUMBER_FIELDS:
                updated[key] = st.number_input(
                    label,
                    value=float(invoice_data.get(key) or 0.0),
                    key=f"{key}::{widget_key}",
                    format="%.2f",
                )
            else:
                updated[key] = st.text_input(
                    label,
                    value=invoice_data.get(key) or "",
                    key=f"{key}::{widget_key}",
                )

    # Positionen (Artikel/Mengen) werden hier nur read-only angezeigt - eine
    # editierbare Tabelle dafür wäre ein separater Schritt.
    if invoice_data.get("positionen"):
        with st.expander("Positionen (Artikel)"):
            st.json(invoice_data["positionen"])

    return updated


def _category_picker(invoice_data: dict, widget_key: str) -> tuple[str, str]:
    """Shows a dropdown pre-filled with the automatically suggested category.

    Returns a tuple (selected_category, suggested_category) so the caller can
    later detect whether the user overrode the automatic suggestion.
    """
    suggested = suggest_category(invoice_data)
    options = CATEGORY_OPTIONS if suggested in CATEGORY_OPTIONS else CATEGORY_OPTIONS + [suggested]
    default_index = options.index(suggested)

    selected = st.selectbox(
        "Kategorie",
        options=options,
        index=default_index,
        key=f"category::{widget_key}",
        help="Automatisch vorgeschlagen – kann bei Bedarf geändert werden.",
    )
    return selected, suggested


def _save_to_db_once(uploaded_file, invoice_data: dict, selected_category: str, suggested_category: str) -> None:
    """Saves an invoice to the database exactly once per uploaded file, even
    if Streamlit reruns this script. Logs a correction entry whenever the
    user picked a different category than the automatic suggestion, so the
    categorizer can be improved later."""
    db_key = f"saved_to_db::{uploaded_file.file_id}"
    invoice_id = save_invoice_to_db(invoice_data, category=selected_category)

    if selected_category != suggested_category:
        save_correction(
            invoice_id=invoice_id,
            old_category=suggested_category,
            new_category=selected_category,
            invoice_data=invoice_data,
        )

    st.session_state[db_key] = invoice_id


if uploaded_files:
    Path("output").mkdir(exist_ok=True)

    if len(uploaded_files) == 1 or not combine_files:
        # Single file, or multiple files processed individually
        for uploaded_file in uploaded_files:
            invoice_data = _process_pdf(uploaded_file)

            st.subheader(f"Erkannte Rechnungsdaten: {uploaded_file.name}")
            invoice_data = _editable_invoice_form(invoice_data, widget_key=uploaded_file.file_id)

            category, suggested_category = _category_picker(invoice_data, widget_key=uploaded_file.file_id)
            invoice_data["category"] = category

            # Use the uploaded PDF's filename for the Excel output
            # (e.g. "Rechnung1.pdf" -> "Rechnung1.xlsx")
            pdf_stem = Path(uploaded_file.name).stem
            output_path = Path("output") / f"{pdf_stem}.xlsx"
            export_to_excel(invoice_data, str(output_path))

            db_key = f"saved_to_db::{uploaded_file.file_id}"
            already_saved = st.session_state.get(db_key) is not None

            col1, col2 = st.columns(2)
            with col1:
                with open(output_path, "rb") as f:
                    st.download_button(
                        label=f"⬇️ Excel herunterladen ({output_path.name})",
                        data=f,
                        file_name=output_path.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"download::{uploaded_file.file_id}",
                    )
            with col2:
                if already_saved:
                    st.button(
                        "✅ In Datenbank gespeichert",
                        disabled=True,
                        key=f"db_done::{uploaded_file.file_id}",
                    )
                else:
                    if st.button("💾 In Datenbank speichern", key=f"db_save::{uploaded_file.file_id}"):
                        _save_to_db_once(uploaded_file, invoice_data, category, suggested_category)
                        st.rerun()

            st.divider()

    else:
        # Multiple files combined into a single Excel file
        invoices_data = []
        categories = {}
        suggested_categories = {}

        for uploaded_file in uploaded_files:
            invoice_data = _process_pdf(uploaded_file)
            invoice_data["source_file"] = uploaded_file.name

            st.subheader(f"Erkannte Rechnungsdaten: {uploaded_file.name}")
            invoice_data = _editable_invoice_form(invoice_data, widget_key=uploaded_file.file_id)

            category, suggested_category = _category_picker(invoice_data, widget_key=uploaded_file.file_id)
            invoice_data["category"] = category
            categories[uploaded_file.file_id] = category
            suggested_categories[uploaded_file.file_id] = suggested_category

            invoices_data.append(invoice_data)

        output_path = Path("output") / "Rechnungen_Sammelexport.xlsx"
        export_multiple_to_excel(invoices_data, str(output_path))

        col1, col2 = st.columns(2)
        with col1:
            with open(output_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ Excel herunterladen ({output_path.name})",
                    data=f,
                    file_name=output_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        with col2:
            if st.button("💾 Alle in Datenbank speichern"):
                for uploaded_file, invoice_data in zip(uploaded_files, invoices_data):
                    db_key = f"saved_to_db::{uploaded_file.file_id}"
                    if st.session_state.get(db_key) is None:
                        _save_to_db_once(
                            uploaded_file,
                            invoice_data,
                            categories[uploaded_file.file_id],
                            suggested_categories[uploaded_file.file_id],
                        )
                st.success("Alle Rechnungen in Datenbank gespeichert ✅")
                st.rerun()

# Optional section: show invoices previously saved to the database
with st.expander("📊 Gespeicherte Rechnungen (Datenbank)"):
    invoices = get_all_invoices()
    if invoices:
        st.dataframe(invoices)
    else:
        st.write("Noch keine Rechnungen in der Datenbank gespeichert.")