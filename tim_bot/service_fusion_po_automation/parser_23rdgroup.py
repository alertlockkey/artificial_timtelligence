# parser_23rdgroup.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def clean_block(value: str) -> str:
    value = value or ""
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s*\n\s*", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_location_name(line1: str, line2: str) -> str:
    # Humana #05526 + Cano Health -> Humana 05526 Cano Health
    line1 = clean(line1).replace("#", "")
    line2 = clean(line2)
    return f"{line1} {line2}".strip()


def parse_23rdgroup_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    wo_match = re.search(r"Work Order #\s*(\d+)", text, re.I)
    nte_match = re.search(r"N\.?T\.?E\.?\s*\$?([\d,]+\.\d{2})", text, re.I)
    schedule_match = re.search(
        r"Schedule Date:\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[AP]M)",
        text,
        re.I,
    )

    location_match = re.search(
        r"Service Location\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(.+?)\s+([A-Z]{2}),?\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    ivr_match = re.search(
        r"IVR Instructions\s*(.+?)\s*Reported Issue",
        text,
        re.DOTALL | re.I,
    )

    issue_match = re.search(
        r"Reported Issue\s*(.+?)\s*\*\*1st Trip Completion Preferred",
        text,
        re.DOTALL | re.I,
    )

    # Fallback from page 3, where the issue appears before Work Order Terms
    if not issue_match:
        issue_match = re.search(
            r"N\.?T\.?E\.?\s*\$?[\d,]+\.\d{2}.*?\n(.+?)\s*\*\*1st Trip Completion Preferred",
            text,
            re.DOTALL | re.I,
        )

    wo_number = wo_match.group(1) if wo_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    service_date = clean(schedule_match.group(1)) if schedule_match else ""

    if location_match:
        location_name = normalize_location_name(
            location_match.group(1),
            location_match.group(2),
        )
        street = clean(location_match.group(3))
        city = clean(location_match.group(4)).title()
        state = clean(location_match.group(5))
        zip_code = clean(location_match.group(6))
    else:
        location_name = ""
        street = ""
        city = ""
        state = "TX"
        zip_code = ""

    job_description = clean(issue_match.group(1)) if issue_match else ""

    if ivr_match:
        notes_for_techs = "IVR Instructions\n" + clean_block(ivr_match.group(1))
    else:
        notes_for_techs = f"""IVR Instructions
MANDATORY Check In/Check Out Process:
To check in:
1. Call 704-823-6108
2. Enter Pin #: 335074 / Enter Job #: {wo_number}
3. Press 1 to check in and then enter number of technicians onsite, press #
To check out:
1. Follow steps 1-2 above
2. Press 1 if job is complete, Press 2 if a return trip is required"""

    return {
        "provider": "23rd Group Facility Services",
        "customer": "23rd Group Facility Services",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": wo_number,
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