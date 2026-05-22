# parser_retailmds.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_location_name(raw: str) -> str:
    raw = clean(raw)

    loc_num = re.search(r"Loc\s*#\s*(\d+)", raw, re.I)
    name_match = re.search(r"\d+\s*-\s*(.+?)\s*-", raw)

    name = clean(name_match.group(1)) if name_match else clean(raw)
    number = loc_num.group(1) if loc_num else ""

    return f"{name} {number}".strip()


def parse_retailmds_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    po_match = re.search(r"VENDOR PO #\s*\n?(\d+-\d+)", text, re.I)
    client_po_match = re.search(r"Client PO #\s*\n?(\d+)", text, re.I)
    nte_match = re.search(r"NTE\s*\$?([\d,]+\.\d{2})", text, re.I)
    priority_match = re.search(r"\n(P\d+)\s*\nDoors/Gates/Glass", text, re.I)
    service_date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{2}\s+\d{1,2}:\d{2}\s*[AP]M)", text, re.I)

    location_match = re.search(
        r"SERVICE LOCATION(?:\s+VENDOR\s+#\s*\d+)?\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    desc_match = re.search(
        r"WORK ORDER DESCRIPTION\s*(.+?)\s*SPECIAL INSTRUCTIONS",
        text,
        re.DOTALL | re.I,
    )

    ivr_phone_match = re.search(r"Dial\s*\(?([\d]{3})\)?-?([\d]{3})-?([\d]{4})", text, re.I)
    ivr_pin_match = re.search(r"Enter IVR Pin#:\s*(\d+)", text, re.I)

    po_number = po_match.group(1) if po_match else ""
    client_po = client_po_match.group(1) if client_po_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    priority = clean(priority_match.group(1)) if priority_match else ""
    service_date = clean(service_date_match.group(1)) if service_date_match else ""

    if location_match:
        raw_location = clean(location_match.group(1))
        location_name = normalize_location_name(raw_location)
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

    scope_text = clean(desc_match.group(1)) if desc_match else ""

    if ivr_phone_match:
        ivr_phone = f"({ivr_phone_match.group(1)})-{ivr_phone_match.group(2)}-{ivr_phone_match.group(3)}"
    else:
        ivr_phone = ""

    ivr_pin = ivr_pin_match.group(1) if ivr_pin_match else ""

    job_description = f"""Issue / Scope:
{scope_text}
"""

    notes_for_techs = f"""IVR INSTRUCTIONS
Check in upon arrival, Check out upon completion

Dial {ivr_phone} Press Option 1 for English

Enter IVR Pin#: {ivr_pin}

If a return visit or quote is necessary, do not IVR as work complete

Check out prompts

Option 1 to > Check out Complete *Only if full scope is 100% completed
Option 2 to > Check out as Return visit Needed
Option 3 to > Check out as Parts Needed
Option 4 to > Check out as Quote Required
"""

    return {
        "provider": "Retail MDS",
        "customer": "Retail MDS",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": po_number,
        "client_po": client_po,
        "approved_cost": approved_cost,
        "priority": priority,
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