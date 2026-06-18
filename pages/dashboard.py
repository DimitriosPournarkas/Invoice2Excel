"""
Dashboard - Auswertung der in der Datenbank gespeicherten Rechnungen.
Wird von Streamlit automatisch als zusätzliche Seite in der Sidebar-Navigation
angezeigt, sobald diese Datei im Ordner "pages/" neben app.py liegt.
"""

import pandas as pd
import streamlit as st

from src.database import get_statistics, get_category_stats

st.set_page_config(page_title="Dashboard", page_icon="📊")

st.title("📊 Dashboard")
st.write("Auswertung aller bisher in der Datenbank gespeicherten Rechnungen.")

stats = get_statistics()

if stats["total_invoices"] == 0:
    st.info("Noch keine Rechnungen in der Datenbank gespeichert. Lade zuerst welche über die Startseite hoch.")
    st.stop()

# --- Gesamt-Statistik ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Anzahl Rechnungen", stats["total_invoices"])
col2.metric("Gesamtbetrag", f"{stats['total_amount']:.2f} €")
col3.metric("Ø Betrag", f"{stats['avg_amount']:.2f} €")
col4.metric("Lieferanten", stats["unique_suppliers"])

st.divider()

# --- Auswertung nach Kategorie ---
st.subheader("Ausgaben nach Kategorie")

category_stats = get_category_stats()

if not category_stats:
    st.info("Den gespeicherten Rechnungen ist noch keine Kategorie zugeordnet.")
else:
    df = pd.DataFrame.from_dict(category_stats, orient="index")
    df.index.name = "Kategorie"
    df = df.sort_values("total", ascending=False)

    st.bar_chart(df["total"])

    display_df = df.rename(columns={
        "count": "Anzahl",
        "total": "Summe (€)",
        "avg": "Ø Betrag (€)",
    })
    display_df["Summe (€)"] = display_df["Summe (€)"].round(2)
    display_df["Ø Betrag (€)"] = display_df["Ø Betrag (€)"].round(2)
    st.dataframe(display_df, use_container_width=True)