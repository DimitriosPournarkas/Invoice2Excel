"""
Dashboard - Auswertung der in der Datenbank gespeicherten Rechnungen.
Wird von Streamlit automatisch als zusätzliche Seite in der Sidebar-Navigation
angezeigt, sobald diese Datei im Ordner "pages/" neben app.py liegt.
"""

import pandas as pd
import streamlit as st

from src.database import (
    get_statistics,
    get_category_stats,
    get_monthly_stats,
    get_top_suppliers,
)

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

# --- Ausgaben nach Kategorie ---
st.subheader("Ausgaben nach Kategorie")

category_stats = get_category_stats()

if not category_stats:
    st.info("Den gespeicherten Rechnungen ist noch keine Kategorie zugeordnet.")
else:
    df_cat = pd.DataFrame.from_dict(category_stats, orient="index")
    df_cat.index.name = "Kategorie"
    df_cat = df_cat.sort_values("total", ascending=False)

    st.bar_chart(df_cat["total"], x_label="Kategorie", y_label="Summe (€)")

    display_cat = df_cat.rename(columns={
        "count": "Anzahl",
        "total": "Summe (€)",
        "avg": "Ø Betrag (€)",
    })
    display_cat["Summe (€)"] = display_cat["Summe (€)"].round(2)
    display_cat["Ø Betrag (€)"] = display_cat["Ø Betrag (€)"].round(2)
    st.dataframe(display_cat, use_container_width=True)

st.divider()

# --- Monatlicher Verlauf ---
st.subheader("Monatlicher Verlauf")

# Jahresfilter
available_years = sorted(
    {row["year"] for row in get_monthly_stats() if row.get("year")},
    reverse=True,
)

if available_years:
    selected_year = st.selectbox(
        "Jahr",
        options=["Alle"] + available_years,
        index=0,
    )

    monthly = get_monthly_stats(
        year=None if selected_year == "Alle" else int(selected_year)
    )

    if monthly:
        df_monthly = pd.DataFrame(monthly)
        df_monthly["Monat"] = df_monthly["month"].astype(str) + "." + df_monthly["year"].astype(str)
        df_monthly = df_monthly.rename(columns={"count": "Anzahl", "total": "Summe (€)"})
        df_monthly = df_monthly.set_index("Monat")

        st.line_chart(df_monthly["Summe (€)"], x_label="Monat", y_label="Summe (€)")

        st.dataframe(
            df_monthly[["Anzahl", "Summe (€)"]].round(2),
            use_container_width=True,
        )
    else:
        st.info("Keine Monatsdaten verfügbar.")
else:
    st.info("Noch keine Datumsdaten vorhanden.")

st.divider()

# --- Top Lieferanten ---
st.subheader("Top Rechnungssteller")

top_n = st.slider("Anzahl anzeigen", min_value=3, max_value=20, value=10)
suppliers = get_top_suppliers(limit=top_n)

if suppliers:
    df_sup = pd.DataFrame(suppliers)
    df_sup = df_sup.rename(columns={
        "lieferant": "Rechnungssteller",
        "count": "Anzahl Rechnungen",
        "total": "Gesamtbetrag (€)",
        "average": "Ø Betrag (€)",
    })
    # WICHTIG: Hier "Rechnungssteller" verwenden (nicht "Lieferant"!)
    df_sup = df_sup.set_index("Rechnungssteller")
    df_sup["Gesamtbetrag (€)"] = df_sup["Gesamtbetrag (€)"].round(2)
    df_sup["Ø Betrag (€)"] = df_sup["Ø Betrag (€)"].round(2)

    st.bar_chart(df_sup["Gesamtbetrag (€)"], x_label="Rechnungssteller", y_label="Gesamtbetrag (€)")
    st.dataframe(df_sup, use_container_width=True)
else:
    st.info("Keine Lieferantendaten verfügbar.")