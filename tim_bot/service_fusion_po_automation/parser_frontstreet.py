# parser_frontstreet.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_location_name(raw: str) -> str:
    raw = clean(raw)

    name_match = re.search(r"(.+?)\s*-\s*Loc", raw, re.I)
    loc_num_match = re.search(r"Loc\s*#\s*(\d+)", raw, re.I)

    name = clean(name_match.group(1)) if name_match else raw
    number = loc_num_match.group(1) if loc_num_match else ""

    return f"{name} {number}".strip()


def parse_frontstreet_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    po_match = re.search(r"VENDOR PO #\s*\n?.*?\n?(\d+-\d+)", text, re.I)
    if not po_match:
        po_match = re.search(r"\b(\d{7}-\d{2})\b", text)

    nte_match = re.search(r"Dispatch NTE\s*\$?([\d,]+\.\d{2})", text, re.I)
    client_po_match = re.search(r"Client PO #\s*(\d+)", text, re.I)
    service_date_match = re.search(
        r"Service Date\s*(\d{1,2}/\d{1,2}/\d{2}\s+\d{1,2}:\d{2}\s*[AP]M)",
        text,
        re.I,
    )

    location_match = re.search(
        r"SERVICE LOCATION\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(?:Suite\s*(.+?)\n)?"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    description_match = re.search(
        r"SERVICE DESCRIPTION\s*(.+?)\s*(?:Print Date|Store Manager|$)",
        text,
        re.DOTALL | re.I,
    )

    ivr_pin_match = re.search(r"(\d{6,})\s*\nIVR Pin #", text, re.I)

    # Some FrontStreet WOs may have a full Check In/Out block.
    check_in_out_match = re.search(
        r"Check In/Out\s*(.+?)(?:SERVICE DESCRIPTION|Store Manager|Print Date|$)",
        text,
        re.DOTALL | re.I,
    )

    po_number = po_match.group(1) if po_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    client_po = client_po_match.group(1) if client_po_match else ""
    service_date = clean(service_date_match.group(1)) if service_date_match else ""

    if location_match:
        raw_location = clean(location_match.group(1))
        location_name = normalize_location_name(raw_location)
        street = clean(location_match.group(2))
        suite_raw = clean(location_match.group(3)) if location_match.group(3) else ""
        suite = re.sub(r"(?i)suite\s*", "", suite_raw).strip()

        # Append suite to street
        if suite:
            street = f"{street} {suite}"
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
    ivr_pin = ivr_pin_match.group(1) if ivr_pin_match else ""

    if check_in_out_match:
        check_in_text = clean(check_in_out_match.group(1))

        if len(check_in_text) < 60:
            notes_for_techs = f"""IVR Check In and Out IS REQUIRED FOR PAYMENT
Call: (516) 500-7776
Pin: {ivr_pin}
"""
        else:
            notes_for_techs = check_in_text
    else:
        notes_for_techs = f"""IVR Check In and Out IS REQUIRED FOR PAYMENT
Call: (516) 500-7776
Pin: {ivr_pin}
"""

    return {
        "provider": "FrontStreet Facility Solutions",
        "customer": "FrontStreet Facility Solutions",
        "location_name": location_name,
        "street": street,
        "suite": suite,
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": po_number,
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