# parser_tcg.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def clean_location_name(raw: str) -> str:
    # Truist - Loc # 103361 -> Truist 103361
    raw = clean(raw)
    loc_match = re.search(r"Loc\s*#\s*(\d+)", raw, re.I)
    name = re.sub(r"\s*-\s*Loc\s*#\s*\d+", "", raw, flags=re.I).strip()
    return f"{name} {loc_match.group(1)}".strip() if loc_match else name


def parse_tcg_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    vendor_po_match = re.search(r"VENDOR PO #\s*\n?.*?(\d{6}-\d{2})", text, re.DOTALL | re.I)
    if not vendor_po_match:
        vendor_po_match = re.search(r"\b(\d{6}-\d{2})\b", text)

    client_po_match = re.search(r"Client PO #\s*(TFC[\w\d.]+)", text, re.I)
    nte_match = re.search(r"NTE\s*\$?([\d,]+\.\d{2})", text, re.I)
    priority_match = re.search(r"\n(0\s*-\s*Days)\nLocks", text, re.I)

    location_match = re.search(
        r"SERVICE LOCATION\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    description_match = re.search(
        r"SERVICE DESCRIPTION\s*(.+?)\s*(?:BILLING INSTRUCTIONS|Store Manager|$)",
        text,
        re.DOTALL | re.I,
    )

    ivr_pin_match = re.search(r"(\d{6,})\s*\nIVR Pin #", text, re.I)

    vendor_po = vendor_po_match.group(1) if vendor_po_match else ""
    client_po = client_po_match.group(1) if client_po_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    priority = clean(priority_match.group(1)) if priority_match else ""

    if location_match:
        location_name = clean_location_name(location_match.group(1))
        street = clean(location_match.group(2))
        city = clean(location_match.group(3)).title()
        state = clean(location_match.group(4))
        zip_code = clean(location_match.group(5))
    else:
        location_name = ""
        street = ""
        city = ""
        state = "TX"
        zip_code = ""

    scope_text = clean(description_match.group(1)) if description_match else ""
    ivr_pin = ivr_pin_match.group(1) if ivr_pin_match else ""

    notes_for_techs = f"""Instructions for Technician:
1. Call to check in with TCG when you arrive at the location.
2. Complete all work listed in description box.
3. If an NTE increase is needed please call TCG for approval.
   - Call 316-321-1244 and speak to your TCG contact for approval.
4. Have manager sign and stamp work order when job is complete.
5. Call to check out when leaving the location.

IVR Pin # {ivr_pin}
"""

    return {
        "provider": "TCG Services",
        "customer": "TCG Services",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": vendor_po,
        "wo_number": client_po,
        "client_po": client_po,
        "approved_cost": approved_cost,
        "priority": priority,
        "service_date": "",
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": scope_text,
        "notes_for_techs": notes_for_techs,
    }