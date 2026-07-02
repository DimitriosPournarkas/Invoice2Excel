# Invoice2Excel
 
A local Python application that automatically extracts structured data from PDF invoices (including scanned documents via OCR) and exports it to Excel. All data is stored in a local SQLite database and can be analyzed via a built-in dashboard.
 
Release: [**Release**](../../releases/latest)
 
---
 
## Usage
 
### Option 1 – Standalone .exe (no Python required)
 
Download the latest `Invoice2Excel.exe` from the [Releases](../../releases/latest) page and double-click to launch. The browser opens automatically after a few seconds.
 
The database (`invoices.db`) will be created in the same folder as the `.exe`.
 
### Option 2 – Run from source
 
```bash
git clone https://github.com/DimitriosPournarkas/Invoice2Excel.git
cd Invoice2Excel
pip install -r requirements.txt
python start.py
```
 
The app opens automatically in your browser at `http://localhost:8501`.
 
### Tesseract OCR (optional)
 
> **Note:** Tesseract OCR is only required for scanned (image-based) PDFs.
> Digitally created PDFs work out of the box without any additional installation.
 
If you need OCR support, install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) and make sure to select the **German language pack (deu)** during setup.
 
---
## Features
 
- **PDF Upload** – Upload one or multiple invoices at once. Use `Ctrl+A` in the file dialog to select an entire folder at once.
- **Folder Scan** – Point the app at a local folder and process all PDFs inside in one click.
- **OCR Support** – Scanned (image-based) PDFs are automatically detected and processed via Tesseract OCR.
- **PDF Preview** – The original invoice is displayed next to the editing form so you can verify extracted data at a glance.
- **Editable Fields** – All extracted fields (date, vendor, amounts, IBAN, line items) can be corrected directly in the browser before saving.
- **Auto-categorization** – Invoices are automatically assigned a category (e.g. *IT / Software*, *Vehicles / Transportation*) based on German and English keywords. The suggestion can always be overridden manually.
- **Duplicate Detection** – If an invoice number already exists in the database, a warning is shown before saving.
- **Excel Export** – Export individual invoices or combine multiple invoices into a single Excel file.
- **SQLite Database** – All invoices are stored locally in `invoices.db`. The schema is automatically migrated when new fields are added.
- **Database Editor** – Edit or delete any invoice directly in the browser, including individual line items.
- **Dashboard** – Visual overview of spending by category, monthly trend (with year filter), and top suppliers.
---
## GUI Screenshots

### Upload of invoice
![App](Pictures/App.png)
![App](Pictures/App2.png)
![App](Pictures/App3.png)
### Datenbankansicht
![Database](Pictures/Database.png)

