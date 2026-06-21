"""
datenbank.py
Seite zum Anzeigen, Bearbeiten und Löschen der in der Datenbank
gespeicherten Rechnungen. Erscheint automatisch als eigener Punkt in der
Streamlit-Sidebar-Navigation (liegt im pages/-Ordner neben app.py).
"""

import streamlit as st
import pandas as pd

from src.database import get_all_invoices, update_invoice, delete_invoice
from src.categorizer import get_categories

st.set_page_config(page_title="Datenbank", page_icon="🗄️")

st.title("🗄️ Datenbank bearbeiten")
st.write("Gespeicherte Rechnungen direkt in der Tabelle korrigieren oder löschen.")

invoices = get_all_invoices()

if not invoices:
    st.info("Noch keine Rechnungen in der Datenbank gespeichert.")
    st.stop()

CATEGORY_OPTIONS = get_categories()

# "positionen" (einzelne Artikel als JSON-Text) wird hier bewusst nicht
# angezeigt - das Bearbeiten einzelner Positionen passiert schon beim
# Hochladen auf der Startseite, hier geht es um die Rechnungs-Kopfdaten.
df = pd.DataFrame(invoices)
if "positionen" in df.columns:
    df = df.drop(columns=["positionen"])

# Lösch-Checkbox-Spalte voranstellen. Sie wird nicht in der DB gespeichert,
# sondern dient nur dazu, Zeilen für den "Markierte löschen"-Button
# auszuwählen (Streamlit-Tabellen haben keine eingebaute Zeilenauswahl).
df.insert(0, "🗑️", False)

COLUMN_CONFIG = {
    "🗑️": st.column_config.CheckboxColumn("Löschen?", width="small"),
    "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
    "rechnungsnummer": st.column_config.TextColumn("Rechnungsnummer"),
    "datum": st.column_config.TextColumn("Datum (TT.MM.JJJJ)"),
    "lieferant": st.column_config.TextColumn("Lieferant"),
    "betrag_netto": st.column_config.NumberColumn("Netto (€)", format="%.2f"),
    "mwst": st.column_config.NumberColumn("MwSt. (€)", format="%.2f"),
    "betrag_brutto": st.column_config.NumberColumn("Brutto (€)", format="%.2f"),
    "iban": st.column_config.TextColumn("IBAN"),
    "category": st.column_config.SelectboxColumn("Kategorie", options=CATEGORY_OPTIONS),
    "tags": st.column_config.TextColumn("Tags"),
    "date_added": st.column_config.TextColumn("Hinzugefügt am", disabled=True),
    "date_updated": st.column_config.TextColumn("Aktualisiert am", disabled=True),
}

edited_df = st.data_editor(
    df,
    column_config=COLUMN_CONFIG,
    num_rows="fixed",
    use_container_width=True,
    hide_index=True,
    key="invoices_editor",
)

col1, col2 = st.columns(2)

with col1:
    if st.button("💾 Änderungen speichern", type="primary"):
        original_by_id = {row["id"]: row for row in invoices}
        editable_columns = [
            c for c in df.columns
            if c not in ("🗑️", "id", "date_added", "date_updated")
        ]

        updated_count = 0
        fehler = []

        for _, edited_row in edited_df.iterrows():
            invoice_id = int(edited_row["id"])
            original_row = original_by_id.get(invoice_id)
            if original_row is None:
                continue

            changed_fields = {}
            for col in editable_columns:
                new_val = edited_row[col]
                if pd.isna(new_val):
                    new_val = None
                old_val = original_row.get(col)
                if new_val != old_val:
                    changed_fields[col] = new_val

            if changed_fields:
                try:
                    update_invoice(invoice_id, **changed_fields)
                    updated_count += 1
                except Exception as e:
                    # z.B. wenn die neue Rechnungsnummer schon vergeben ist
                    # (rechnungsnummer ist UNIQUE in der DB)
                    fehler.append((invoice_id, str(e)))

        if updated_count:
            st.success(f"{updated_count} Rechnung(en) aktualisiert ✅")
        if fehler:
            with st.expander(f"⚠️ {len(fehler)} Fehler beim Speichern"):
                for invoice_id, err in fehler:
                    st.write(f"**ID {invoice_id}**: {err}")
        if updated_count or fehler:
            st.rerun()
        else:
            st.info("Keine Änderungen erkannt.")

with col2:
    if st.button("🗑️ Markierte löschen"):
        to_delete = edited_df[edited_df["🗑️"] == True]["id"].tolist()
        if not to_delete:
            st.warning("Keine Zeilen zum Löschen markiert.")
        else:
            for invoice_id in to_delete:
                delete_invoice(int(invoice_id))
            st.success(f"{len(to_delete)} Rechnung(en) gelöscht ✅")
            st.rerun()