# parser_dhpace.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_dhpace_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    po_match = re.search(r"\b(P\d{6,})\b", text, re.I)
    wo_match = re.search(r"Work Order #\s*\n?\s*(WOT\d+)", text, re.I)
    nte_match = re.search(r"NTE TOTAL\s*\n?\[USD\]\s*\n?\s*([\d,]+\.\d{2})", text, re.I)
    scheduled_match = re.search(r"SCHEDULED\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})", text, re.I)

    customer_match = re.search(r"Customer\s+(.+)", text, re.I)
    store_match = re.search(r"Store#\s+(.+)", text, re.I)
    address_match = re.search(
        r"Address\s+(.+?)\s*\n"
        r"([A-Za-z ]+),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.I,
    )

    desc_match = re.search(
        r"Problem\s*\n?Description\s*(.+?)\s*By accepting",
        text,
        re.DOTALL | re.I,
    )

    dhpace_contact_match = re.search(r"DHPace:\s*(.+?)(?:\n|$)", text, re.I)

    po_number = po_match.group(1) if po_match else ""
    wo_number = wo_match.group(1) if wo_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    service_date = scheduled_match.group(1) if scheduled_match else ""

    customer_site = clean(customer_match.group(1)) if customer_match else ""
    store_number = clean(store_match.group(1)) if store_match else ""

    location_name = f"{customer_site} {store_number}".strip()

    if address_match:
        street = clean(address_match.group(1))
        city = clean(address_match.group(2)).title()
        state = clean(address_match.group(3))
        zip_code = clean(address_match.group(4))
    else:
        street = ""
        city = ""
        state = "TX"
        zip_code = ""

    scope_text = clean(desc_match.group(1)) if desc_match else ""
    dhpace_contact = clean(dhpace_contact_match.group(1)) if dhpace_contact_match else ""

    job_description = scope_text

    notes_for_techs = f"""DHPace:
{dhpace_contact}

NTE adjustments can be made while on site. Vendors must submit an itemized quote or call for additional work authorizations.
"""

    return {
        "provider": "DH Pace",
        "customer": "DH Pace",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": wo_number,
        "approved_cost": approved_cost,
        "service_date": service_date,
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": job_description,
        "notes_for_techs": notes_for_techs,
    }