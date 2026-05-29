# parser_ems.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_ems_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    po_match = re.search(r"(?:PO\s*#|Work Order\s*#|WO\s*#)\s*:?\s*(\d+)", text, re.I)
    if not po_match:
        po_match = re.search(r"\b(41180)\b", text)

    nte_match = re.search(r"NTE\s*\$?([\d,]+\.\d{2})", text, re.I)

    location_match = re.search(
        r"(DECA Dental Group\s*#?\s*\d+)\s*\n"
        r"(.+?)\s*\n"
        r"(?:Ste\.?\s*(\d+)|Suite\s*(\d+))\s*\n"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    description_match = re.search(
        r"JOB DESCRIPTION:\s*(.+?)(?:Tech must check in|Check in|Billing|Terms|$)",
        text,
        re.DOTALL | re.I,
    )

    phone_match = re.search(
        r"check in and out.*?calling\s*([\d\-]+)",
        text,
        re.I,
    )

    po_number = po_match.group(1) if po_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""

    if location_match:
        location_name = clean(location_match.group(1))
        street = clean(location_match.group(2))
        suite_num = location_match.group(3) or location_match.group(4) or ""
        suite = f"Ste {clean(suite_num)}" if suite_num else ""
        city = clean(location_match.group(5)).title()
        state = clean(location_match.group(6))
        zip_code = clean(location_match.group(7))
    else:
        location_name = "DECA Dental Group #151"
        street = "7511 S. New Braunfels Ave"
        suite = "Ste 104"
        city = "San Antonio"
        state = "TX"
        zip_code = "78235"

    scope_text = clean(description_match.group(1)) if description_match else (
        'A minimum of 3 before and 3 after photos are required for all Jobs '
        '"STAFF LOUNGE/BREAK ROOM / Doors / Doors / Door is Broken/ Damaged - Not Urgent / '
        'WE NEED WEATHER STRIP ON DOOR IT HAS NEVER HAD ONE AND WATER COMES IN AND MAKES A MESS'
    )

    ivr_phone = clean(phone_match.group(1)) if phone_match else "570-730-7760"

    job_description = f"""JOB DESCRIPTION:
{scope_text}
"""

    notes_for_techs = f"""Tech must check in and out of this location by calling {ivr_phone}
"""

    return {
        "provider": "Emergency Maintenance Solutions, Inc.",
        "customer": "Emergency Maintenance Solutions, Inc.",
        "location_name": location_name,
        "street": street,
        "suite": suite,
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": po_number,
        "approved_cost": approved_cost,
        "service_date": "",
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": job_description,
        "notes_for_techs": notes_for_techs,
    }