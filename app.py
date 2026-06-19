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

# --- Datei-Upload ---
uploaded_files = st.file_uploader(
    "PDF-Rechnung(en) auswählen", type=["pdf"], accept_multiple_files=True
)

combine_files = False
if uploaded_files and len(uploaded_files) > 1:
    combine_files = st.checkbox(
        "Alle Rechnungen in eine Excel-Datei zusammenfassen", value=False
    )

# --- Ordner scannen ---
st.divider()
st.subheader("📂 Ordner scannen")
st.write("Alle PDFs in einem lokalen Ordner auf einmal einlesen und direkt in DB speichern.")

folder_path = st.text_input(
    "Ordnerpfad",
    placeholder=r"z.B. C:\Rechnungen\2026",
    help="Absoluter Pfad zum Ordner mit den PDF-Rechnungen.",
)

scan_clicked = st.button("🔍 Ordner scannen", disabled=not folder_path)

if scan_clicked and folder_path:
    folder = Path(folder_path.strip())
    if not folder.exists():
        st.error(f"Ordner nicht gefunden: {folder}")
    elif not folder.is_dir():
        st.error(f"Das ist kein Ordner: {folder}")
    else:
        pdf_files = sorted(folder.glob("*.pdf"))
        if not pdf_files:
            st.warning(f"Keine PDF-Dateien in {folder} gefunden.")
        else:
            st.info(f"{len(pdf_files)} PDF(s) gefunden – werden jetzt verarbeitet...")
            Path("output").mkdir(exist_ok=True)
            erfolge = 0
            fehler = []
            fortschritt = st.progress(0)

            for i, pdf_path in enumerate(pdf_files):
                try:
                    text = extract_text_from_pdf(str(pdf_path))
                    invoice_data = parse_invoice(text)
                    invoice_data["source_file"] = pdf_path.name

                    category = suggest_category(invoice_data)
                    invoice_data["category"] = category

                    output_path = Path("output") / f"{pdf_path.stem}.xlsx"
                    export_to_excel(invoice_data, str(output_path))
                    save_invoice_to_db(invoice_data, category=category)
                    erfolge += 1

                except Exception as e:
                    fehler.append((pdf_path.name, str(e)))

                fortschritt.progress((i + 1) / len(pdf_files))

            if erfolge:
                st.success(
                    f"{erfolge} Rechnung(en) verarbeitet, als Excel exportiert "
                    f"und in DB gespeichert ✅"
                )
            if fehler:
                with st.expander(f"⚠️ {len(fehler)} Fehler beim Verarbeiten"):
                    for name, err in fehler:
                        st.write(f"**{name}**: {err}")

st.divider()

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
    updated = dict(invoice_data)

    scalar_keys = [
        key for key, value in invoice_data.items()
        if key != "positionen"
        and key not in EXCLUDED_FIELDS
        and not isinstance(value, (list, dict))
    ]
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

    if invoice_data.get("positionen"):
        with st.expander("Positionen (Artikel)"):
            st.json(invoice_data["positionen"])

    return updated


def _category_picker(invoice_data: dict, widget_key: str) -> tuple[str, str]:
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
        for uploaded_file in uploaded_files:
            invoice_data = _process_pdf(uploaded_file)

            st.subheader(f"Erkannte Rechnungsdaten: {uploaded_file.name}")
            invoice_data = _editable_invoice_form(invoice_data, widget_key=uploaded_file.file_id)

            category, suggested_category = _category_picker(invoice_data, widget_key=uploaded_file.file_id)
            invoice_data["category"] = category

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