"""
extractor.py
Zuständig für das Einlesen von PDF-Dateien und das Extrahieren von Rohtext
sowie Tabellen mithilfe von pdfplumber.
"""

import pdfplumber


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Liest eine PDF-Datei ein und gibt den gesamten enthaltenen Text zurück.

    Args:
        pdf_path: Pfad zur PDF-Datei.

    Returns:
        Der extrahierte Text als String (alle Seiten zusammengefügt).
    """
    full_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text.append(page_text)

    return "\n".join(full_text)


def extract_tables_from_pdf(pdf_path: str) -> list:
    """
    Liest eine PDF-Datei ein und gibt alle gefundenen Tabellen zurück.

    Args:
        pdf_path: Pfad zur PDF-Datei.

    Returns:
        Eine Liste von Tabellen, jede Tabelle ist eine Liste von Zeilen
        (jede Zeile eine Liste von Zellen-Strings).
    """
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                all_tables.append(table)

    return all_tables


if __name__ == "__main__":
    # Kleiner manueller Test
    import sys

    if len(sys.argv) < 2:
        print("Nutzung: python extractor.py <pfad_zur_pdf>")
    else:
        text = extract_text_from_pdf(sys.argv[1])
        print("--- Extrahierter Text ---")
        print(text)
