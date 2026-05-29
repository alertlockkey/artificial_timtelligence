# parser_broadway_national.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_broadway_national_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    po_match = re.search(r"Tracking #\s*(\d+)", text, re.I)
    nte_match = re.search(r"NTE\s*\$?([\d,]+\.\d{2})", text, re.I)
    priority_match = re.search(r"Priority\s*(.+)", text, re.I)
    assigned_match = re.search(r"Assigned To\s*(.+)", text, re.I)
    assigned_phone_match = re.search(r"Phone #\s*(\+?[\d\s\-\(\)]+)", text, re.I)
    date_match = re.search(r"WO Date\s*(\d{1,2}/\d{1,2}/\d{4})", text, re.I)

    location_match = re.search(
        r"Service Location\s*\n"
        r"(.+?)\n"          # parent/client, ex: MillerKnoll
        r"(.+?)\n"          # store/name, ex: DWR
        r"#\s*(\d+)\n"      # location number
        r"(.+?)\n"          # street
        r"Suite\s*(.+?)\n"  # suite
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    scope_match = re.search(
        r"Scope of Work\s*(.+?)\s*Service Instructions",
        text,
        re.DOTALL | re.I,
    )

    ivr_phone_match = re.search(
        r"IVR Phone Number\s*\n?(.+?)\s*Vendor ID",
        text,
        re.DOTALL | re.I,
    )
    vendor_id_match = re.search(r"Vendor ID\s*\n?(\d+)", text, re.I)
    ivr_pin_match = re.search(r"Umbrava IVR PIN\s*\n?(\d+)", text, re.I)

    po_number = po_match.group(1) if po_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    priority = clean(priority_match.group(1)) if priority_match else ""
    assigned_to = clean(assigned_match.group(1)) if assigned_match else ""
    assigned_phone = clean(assigned_phone_match.group(1)) if assigned_phone_match else ""
    service_date = date_match.group(1) if date_match else ""

    if location_match:
        store_name = clean(location_match.group(2))
        location_number = clean(location_match.group(3))
        location_name = f"{store_name} {location_number}"
        street = clean(location_match.group(4))
        suite = clean(location_match.group(5))
        city = clean(location_match.group(6)).title()
        state = clean(location_match.group(7))
        zip_code = clean(location_match.group(8))
    else:
        location_name = ""
        street = ""
        suite = ""
        city = ""
        state = "TX"
        zip_code = ""

    scope_text = clean(scope_match.group(1)) if scope_match else ""

    ivr_phone = clean(ivr_phone_match.group(1)) if ivr_phone_match else ""
    vendor_id = clean(vendor_id_match.group(1)) if vendor_id_match else ""
    ivr_pin = clean(ivr_pin_match.group(1)) if ivr_pin_match else ""

    job_description = scope_text

    notes_for_techs = f"""IVR Phone Number {ivr_phone}
Vendor ID {vendor_id}
Umbrava IVR PIN {ivr_pin}
"""

    return {
        "provider": "Broadway National",
        "customer": "Broadway National",
        "location_name": location_name,
        "street": street,
        "suite": suite,
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": po_number,
        "approved_cost": approved_cost,
        "priority": priority,
        "service_date": service_date,
        "assigned_to": assigned_to,
        "assigned_phone": assigned_phone,
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": job_description,
        "notes_for_techs": notes_for_techs,
    }