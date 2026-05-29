# parser_prs.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_location_name(raw: str) -> str:
    # SPEEDY CASH - Loc # 51689 -> SPEEDY CASH 51689
    raw = clean(raw)
    match = re.search(r"(.+?)\s*-\s*Loc\s*#\s*(\d+)", raw, re.I)

    if match:
        return f"{clean(match.group(1))} {clean(match.group(2))}"

    return raw


def parse_prs_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    vendor_po_match = re.search(r"VENDOR PO #.*?\n?(\d{6}-\d{2})", text, re.DOTALL | re.I)
    if not vendor_po_match:
        vendor_po_match = re.search(r"\b(\d{6}-\d{2})\b", text)

    client_po_match = re.search(r"Client PO #\s*\n?(\d+)", text, re.I)
    nte_match = re.search(r"NTE\s*\$?([\d,]+\.\d{2})", text, re.I)
    service_date_match = re.search(r"Service Date\s*(\d{1,2}/\d{1,2}/\d{2})", text, re.I)

    location_match = re.search(
        r"SERVICE LOCATION\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(#\d+)\n"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    description_match = re.search(
        r"SERVICE DESCRIPTION\s*(.+?)\s*SPECIAL INSTRUCTIONS",
        text,
        re.DOTALL | re.I,
    )

    special_match = re.search(
        r"SPECIAL INSTRUCTIONS\s*(.+?)\s*(?:Immediate Hazard|BILLING INSTRUCTIONS|Store Manager|$)",
        text,
        re.DOTALL | re.I,
    )

    vendor_po = vendor_po_match.group(1) if vendor_po_match else ""
    client_po = client_po_match.group(1) if client_po_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    service_date = clean(service_date_match.group(1)) if service_date_match else ""

    if location_match:
        location_name = normalize_location_name(location_match.group(1))
        street = clean(location_match.group(2))
        suite = clean(location_match.group(3))
        city = clean(location_match.group(4)).title()
        state = clean(location_match.group(5))
        zip_code = clean(location_match.group(6))
    else:
        location_name = ""
        street = ""
        suite = ""
        city = ""
        state = "TX"
        zip_code = ""

    scope_text = clean(description_match.group(1)) if description_match else ""
    notes_for_techs = clean(special_match.group(1)) if special_match else ""

    return {
        "provider": "Professional Retail Services",
        "customer": "Professional Retail Services",
        "location_name": location_name,
        "street": street,
        "suite": suite,
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": vendor_po,
        "wo_number": vendor_po,
        "client_po": client_po,
        "approved_cost": approved_cost,
        "service_date": service_date,
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": scope_text,
        "notes_for_techs": notes_for_techs,
    }