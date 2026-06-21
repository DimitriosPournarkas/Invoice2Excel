"""
categorizer.py
Automatic category suggestions for invoices.
Completely independent of parser and database.
Provides suggestions only - user makes the final decision.
"""

import re
from typing import List, Dict, Optional


# =========================================================
# Category Definitions
#
# Keywords are matched against German invoice text, so each category
# carries German terms as the primary set. English terms are kept
# alongside them since some vendors (especially IT/SaaS) use English
# product names and line items even on German invoices.
# =========================================================

CATEGORIES = {
    "IT / Software": {
        "keywords": [
            # Deutsch
            "software", "lizenz", "cloud", "hosting", "server",
            "entwicklung", "programmierung", "datenbank",
            "wartung", "support", "kundendienst", "abonnement",
            "verlängerung", "domain", "webseite", "webhosting",
            # English
            "license", "development", "programming", "api", "database",
            "aws", "azure", "google cloud", "microsoft", "adobe",
            "jetbrains", "github", "gitlab", "jira", "confluence",
            "saas", "paas", "iaas", "subscription", "renewal",
            "maintenance", "helpdesk", "service desk"
        ],
        "weight": 2
    },
    "Office / Administration": {
        "keywords": [
            # Deutsch
            "büro", "büromaterial", "büroartikel", "papier", "drucker",
            "toner", "schreibtisch", "stuhl", "ablage", "umschlag",
            "versand", "porto", "reinigung",
            # English
            "office", "supplies", "printer", "desk", "chair",
            "filing", "stationery", "envelope", "shipping",
            "postage", "mailing", "janitorial"
        ],
        "weight": 1
    },
    "Marketing / Advertising": {
        "keywords": [
            # Deutsch
            "werbung", "anzeige", "soziale medien", "inhalt",
            "newsletter", "kampagne", "grafik", "agentur", "kreativ",
            "marketingagentur", "webdesign",
            # English
            "marketing", "advertising", "ad", "facebook", "instagram",
            "google ads", "seo", "sem", "content", "blog",
            "email marketing", "campaign", "branding", "design",
            "graphic", "video", "production", "creative"
        ],
        "weight": 1
    },
    "Consulting / Professional Services": {
        "keywords": [
            # Deutsch
            "beratung", "beratungsleistung", "berater", "strategie",
            "coaching", "schulung", "workshop", "gutachten",
            "bewertung", "prüfung", "wirtschaftsprüfung", "moderation",
            # English
            "consulting", "consultancy", "advisory", "analysis",
            "training", "facilitation", "mediation", "expertise",
            "assessment", "evaluation", "review", "audit", "compliance"
        ],
        "weight": 1
    },
    "Purchases / Inventory": {
        "keywords": [
            # Deutsch
            "einkauf", "produkt", "material", "lieferung", "bestellung",
            "komponente", "rohmaterial", "verpackung", "logistik",
            "lager", "bestand", "teile", "ausrüstung", "maschinen",
            "ersatzteile", "zubehör",
            # English
            "purchase", "product", "delivery", "order", "component",
            "raw material", "packaging", "warehouse", "inventory",
            "stock", "parts", "equipment", "machinery", "tools"
        ],
        "weight": 1
    },
    "Travel / Expenses": {
        "keywords": [
            # Deutsch
            "reise", "hotel", "flug", "zug", "unterkunft", "frühstück",
            "verpflegung", "taxi", "mietwagen", "parken", "maut",
            "kilometerpauschale", "fahrkarte", "geschäftsreise",
            "spesen", "bahnticket", "übernachtung",
            # English
            "travel", "flight", "train", "accommodation",
            "breakfast", "meal", "per diem", "rental car", "parking",
            "toll", "mileage", "ticket", "transportation", "business trip"
        ],
        "weight": 1
    },
    "Insurance": {
        "keywords": [
            # Deutsch
            "versicherung", "haftpflicht", "rechtsschutz",
            "sachversicherung", "inhaltsversicherung",
            "fahrzeugversicherung", "unfall", "berufshaftpflicht",
            "police", "prämie", "betriebsversicherung",
            "krankenversicherung", "kfz-versicherung",
            # English
            "liability", "legal protection", "property", "content",
            "vehicle", "accident", "professional liability", "premium",
            "business insurance", "workers comp", "health"
        ],
        "weight": 1
    },
    "Taxes / Fees": {
        "keywords": [
            # Deutsch
            "steuer", "steuern", "finanzamt", "gebühr", "lizenzgebühr",
            "anmeldung", "genehmigung", "grundsteuer", "lohnsteuer",
            "umsatzsteuer", "zoll", "steuernummer", "ust-id",
            # English
            "tax", "taxes", "irs", "tax office", "assessment",
            "fee", "license fee", "registration", "permit",
            "property tax", "payroll tax", "sales tax",
            "tariff", "duty", "customs"
        ],
        "weight": 1
    },
    "Rent / Real Estate": {
        "keywords": [
            # Deutsch
            "miete", "pacht", "immobilie", "gebäude", "büroraum",
            "lagerhalle", "nebenkosten", "strom", "wasser", "gas",
            "internet", "telefon", "festnetz", "kaution",
            # English
            "rent", "lease", "property", "building",
            "office space", "warehouse", "storage",
            "maintenance fee", "utilities", "electricity",
            "water", "phone", "landline"
        ],
        "weight": 1
    },
    "Personnel / Payroll": {
        "keywords": [
            # Deutsch
            "gehalt", "lohn", "vergütung", "mitarbeiter", "personal",
            "sozialversicherung", "rente", "bonus", "überstunden",
            "sozialleistungen", "lohnabrechnung",
            # English
            "payroll", "salary", "wages", "compensation",
            "employee", "staff", "worker", "social security",
            "health insurance", "pension", "overtime", "benefits", "401k"
        ],
        "weight": 1
    },
    "Training / Education": {
        "keywords": [
            # Deutsch
            "schulung", "weiterbildung", "fortbildung", "seminar",
            "kurs", "zertifizierung", "konferenz", "tagung",
            "akademie", "lernen", "webinar", "ausbildung",
            # English
            "training", "education", "professional development",
            "course", "certification", "workshop",
            "conference", "summit", "academy", "learning",
            "e-learning", "tutorial"
        ],
        "weight": 1
    },
    "Healthcare / Medical": {
        "keywords": [
            # Deutsch
            "medizinisch", "gesundheit", "zahn", "arzt", "krankenhaus",
            "klinik", "apotheke", "rezept", "therapie", "reha",
            "gesundheitswesen", "untersuchung", "facharzt",
            # English
            "medical", "health", "dental", "vision", "doctor",
            "hospital", "clinic", "pharmacy", "prescription",
            "rehabilitation", "healthcare", "wellness", "examination"
        ],
        "weight": 1
    },
    "Legal / Law": {
        "keywords": [
            # Deutsch
            "rechtlich", "anwalt", "rechtsanwalt", "rechtsberatung",
            "vertrag", "vereinbarung", "klage", "vergleich",
            "geistiges eigentum", "marke", "patent", "urheberrecht",
            "kanzlei", "notar",
            # English
            "legal", "lawyer", "attorney", "legal services",
            "agreement", "litigation", "settlement",
            "intellectual property", "trademark", "copyright",
            "legal advice", "legal counsel"
        ],
        "weight": 1
    },
    "Vehicles / Transportation": {
        "keywords": [
            # Deutsch
            "fahrzeug", "auto", "pkw", "lkw", "transporter", "flotte",
            "wartung", "reparatur", "werkstatt", "inspektion",
            "tankstelle", "benzin", "diesel", "kraftstoff", "öl",
            "reifen", "batterie", "zulassung", "maut", "parken",
            "klimaanlage", "kältemittel", "tüv", "hauptuntersuchung",
            "kfz", "autowerkstatt",
            # English
            "vehicle", "car", "truck", "van", "fleet",
            "repair", "service", "inspection",
            "fuel", "gas", "oil", "tires", "battery",
            "registration", "toll", "parking"
        ],
        "weight": 1
    },
    "Utilities / Telecom": {
        "keywords": [
            # Deutsch
            "strom", "wasser", "gas", "heizung", "internet", "telefon",
            "mobilfunk", "telekommunikation", "festnetz",
            "müllentsorgung", "entsorgung", "stadtwerke",
            # English
            "electricity", "broadband", "phone", "mobile",
            "telecom", "telephone", "cellular", "voip",
            "waste disposal", "recycling", "sanitation"
        ],
        "weight": 1
    },
    "Membership / Subscriptions": {
        "keywords": [
            # Deutsch
            "mitgliedschaft", "abonnement", "jahresbeitrag", "verband",
            "berufsverband", "industrie- und handelskammer", "ihk",
            "netzwerk", "beitrag", "verlängerung", "anmeldung",
            # English
            "membership", "subscription", "annual fee",
            "association", "professional organization",
            "chamber of commerce", "alliance",
            "dues", "renewal", "enrollment"
        ],
        "weight": 1
    },
    "Banking / Finance": {
        "keywords": [
            # Deutsch
            "bank", "bankwesen", "kredit", "zinsen", "hypothek",
            "finanzierung", "investition", "aktie", "handel",
            "dividende", "kapital", "finanzdienstleistung",
            "vermögensverwaltung", "kontoführung",
            # English
            "banking", "loan", "interest", "mortgage", "financing",
            "investment", "stock", "trading", "dividend", "capital",
            "financial services", "asset management"
        ],
        "weight": 1
    },
    "Other": {
        "keywords": [],
        "weight": 0
    }
}

# Category list for dropdown menus
CATEGORY_LIST = list(CATEGORIES.keys())


# =========================================================
# Suggestion Functions
# =========================================================

def suggest_category(invoice_data: dict) -> str:
    """
    Suggests a category based on invoice data.
    
    The suggestion is just a recommendation - the user makes
    the final decision in the UI.
    
    Args:
        invoice_data: Parsed invoice dictionary from parser.py
    
    Returns:
        Suggested category name (e.g., "IT / Software")
    """
    # Combine all text for analysis
    text = " ".join([
        invoice_data.get("lieferant") or "",
        invoice_data.get("rechnungsnummer") or "",
        " ".join([p.get("artikel") or "" for p in invoice_data.get("positionen") or []])
    ]).lower()
    
    # If no text, return "Other"
    if not text:
        return "Other"
    
    # Calculate scores for each category
    scores = {}
    for category, config in CATEGORIES.items():
        score = 0
        for keyword in config["keywords"]:
            # Count occurrences of each keyword
            occurrences = len(re.findall(rf'\b{re.escape(keyword)}\b', text))
            if occurrences > 0:
                score += occurrences * config["weight"]
        if score > 0:
            scores[category] = score
    
    # Return best matching category
    if scores:
        return max(scores, key=scores.get)
    
    return "Other"


def suggest_tags(invoice_data: dict) -> List[str]:
    """
    Suggests automatic tags based on invoice data.
    
    Returns:
        List of tag strings (e.g., ["2026", "Muster", "software"])
    """
    tags = []
    
    # Extract year from date
    if invoice_data.get("datum"):
        date_parts = invoice_data["datum"].split(".")
        if len(date_parts) == 3:
            year = date_parts[2]
            if len(year) == 4:
                tags.append(year)
    
    # Extract vendor as tag
    if invoice_data.get("lieferant"):
        # Take first word of vendor name
        vendor = invoice_data["lieferant"].split()[0]
        if vendor:
            tags.append(vendor)
    
    # Extract first category keyword if available
    text = " ".join([p.get("artikel") or "" for p in invoice_data.get("positionen") or []])
    if text:
        # Find first keyword from categories
        for category, config in CATEGORIES.items():
            for keyword in config["keywords"]:
                if keyword in text.lower():
                    tags.append(keyword)
                    break
            if tags:
                break
    
    # Remove duplicates and return
    return list(dict.fromkeys(tags))


def suggest_category_with_confidence(invoice_data: dict) -> Dict[str, float]:
    """
    Returns all categories with confidence scores (0-100).
    
    Useful for showing multiple options to the user.
    
    Returns:
        Dictionary of {category: confidence_score}
    """
    text = " ".join([
        invoice_data.get("lieferant") or "",
        invoice_data.get("rechnungsnummer") or "",
        " ".join([p.get("artikel") or "" for p in invoice_data.get("positionen") or []])
    ]).lower()
    
    if not text:
        return {"Other": 100.0}
    
    # Calculate scores
    scores = {}
    total_score = 0
    
    for category, config in CATEGORIES.items():
        score = 0
        for keyword in config["keywords"]:
            occurrences = len(re.findall(rf'\b{re.escape(keyword)}\b', text))
            if occurrences > 0:
                score += occurrences * config["weight"]
        scores[category] = score
        total_score += score
    
    # Convert to percentages
    if total_score > 0:
        return {cat: (score / total_score * 100) for cat, score in scores.items() if score > 0}
    
    return {"Other": 100.0}


# =========================================================
# Category Management
# =========================================================

def get_categories() -> List[str]:
    """
    Returns all available categories.
    
    Returns:
        List of category names
    """
    return CATEGORY_LIST


def add_category(category: str, keywords: List[str], weight: int = 1):
    """
    Adds a new category (for user customization).
    
    Args:
        category: Category name
        keywords: List of keywords for matching
        weight: Priority weight (1-3)
    """
    if category not in CATEGORIES:
        CATEGORIES[category] = {
            "keywords": [kw.lower() for kw in keywords],
            "weight": min(max(weight, 1), 3)
        }
        CATEGORY_LIST.append(category)


def remove_category(category: str):
    """
    Removes a category (for user customization).
    """
    if category in CATEGORIES and category != "Other":
        del CATEGORIES[category]
        if category in CATEGORY_LIST:
            CATEGORY_LIST.remove(category)


# =========================================================
# Testing
# =========================================================

if __name__ == "__main__":
    # Test data
    test_invoice = {
        "rechnungsnummer": "INV-2026-001",
        "datum": "13.06.2026",
        "lieferant": "Microsoft Corporation",
        "betrag_netto": 100.00,
        "mwst": 19.00,
        "betrag_brutto": 119.00,
        "iban": "DE89370400440532013000",
        "positionen": [
            {"artikel": "Microsoft 365 Business Premium License", "menge": 2, "einzelpreis": 50.0, "gesamtpreis": 100.0}
        ],
    }
    
    # Test category suggestion
    print("=== Category Suggestion ===")
    print(f"Suggested: {suggest_category(test_invoice)}")
    
    # Test tags suggestion
    print("\n=== Tags Suggestion ===")
    print(f"Tags: {suggest_tags(test_invoice)}")
    
    # Test confidence scores
    print("\n=== Confidence Scores ===")
    for cat, score in suggest_category_with_confidence(test_invoice).items():
        if score > 0:
            print(f"  {cat}: {score:.1f}%")
    
    # Test all categories
    print("\n=== All Categories ===")
    for cat in get_categories():
        print(f"  - {cat}")