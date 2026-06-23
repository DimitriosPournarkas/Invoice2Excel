"""
extractor.py
Responsible for reading PDF files and extracting raw text
as well as tables using pdfplumber.

For scanned PDFs (no embedded text), it automatically switches to OCR
using Tesseract. Tesseract must be installed:
https://github.com/UB-Mannheim/tesseract/wiki
"""

import pdfplumber

# Minimum character count per page - if the extracted text falls below this,
# the page is classified as a scan and reprocessed via OCR.
_MIN_TEXT_LENGTH = 50

# Path to Tesseract executable on Windows. Adjust if installed elsewhere.
_TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _ocr_available() -> bool:
    """Checks if pytesseract and pdf2image are installed."""
    try:
        import pytesseract
        import pdf2image
        return True
    except ImportError:
        return False


def _ocr_page(pdf_path: str, page_number: int) -> str:
    """
    Performs OCR on a single PDF page.

    Args:
        pdf_path: Path to the PDF file.
        page_number: Page number (1-based).

    Returns:
        Recognized text from the page.
    """
    import pytesseract
    from pdf2image import convert_from_path

    # Set Tesseract path here, inside the function, so the module-level
    # import of extractor.py never fails even if pytesseract is not installed.
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD

    images = convert_from_path(
        pdf_path,
        first_page=page_number,
        last_page=page_number,
        dpi=300,
    )
    if not images:
        return ""

    return pytesseract.image_to_string(images[0], lang="deu")


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Reads a PDF file and returns all contained text.

    For each page, pdfplumber is used first. If a page contains
    too little text (scan or image-based PDF), OCR with Tesseract
    is automatically used as a fallback - provided that pytesseract and
    pdf2image are installed. Otherwise, a warning is printed.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        The extracted text as a string (all pages concatenated).
    """
    full_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""

            if len(page_text.strip()) >= _MIN_TEXT_LENGTH:
                full_text.append(page_text)
            else:
                # Page has no usable text → OCR required
                if _ocr_available():
                    ocr_text = _ocr_page(pdf_path, page_number)
                    if ocr_text.strip():
                        full_text.append(ocr_text)
                else:
                    print(
                        f"[extractor] Page {page_number} appears to be a scan, "
                        f"but pytesseract/pdf2image are not installed. "
                        f"OCR will be skipped.\n"
                        f"Installation: pip install pytesseract pdf2image\n"
                        f"Tesseract: https://github.com/UB-Mannheim/tesseract/wiki"
                    )

    return "\n".join(full_text)


def extract_tables_from_pdf(pdf_path: str) -> list:
    """
    Reads a PDF file and returns all found tables.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        A list of tables, each table is a list of rows
        (each row is a list of cell strings).
    """
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                all_tables.append(table)

    return all_tables


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extractor.py <path_to_pdf>")
    else:
        text = extract_text_from_pdf(sys.argv[1])
        print("--- Extracted Text ---")
        print(text)