# parser_buckle.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_buckle_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    wo_match = re.search(r"Work Order #\s*(\d+)", text, re.I)
    priority_match = re.search(r"Priority:\s*(.+)", text, re.I)
    schedule_match = re.search(r"Schedule Date:\s*([\d/]+)\s*([\d:]+\s*[AP]M)", text, re.I)
    nte_match = re.search(r"NTE:\s*\$?([\d,]+\.\d{2})", text, re.I)

    site_match = re.search(
        r"Site:\s*\n"
        r"(.+?)\s*\n"
        r"(.+?)\s*\n"
        r"(.+?)\s*\n"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    description_match = re.search(
        r"Work Order Description:\s*(.+?)\s*Assignment Scope:",
        text,
        re.DOTALL | re.I,
    )

    scope_match = re.search(
        r"Assignment Scope:\s*(.+?)\s*Work Order Special Instructions:",
        text,
        re.DOTALL | re.I,
    )

    instructions_match = re.search(
        r"Work Order Special Instructions:\s*(.+)$",
        text,
        re.DOTALL | re.I,
    )

    wo_number = wo_match.group(1) if wo_match else ""
    priority = clean(priority_match.group(1)) if priority_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""

    service_date = schedule_match.group(1) if schedule_match else ""
    service_time = schedule_match.group(2) if schedule_match else ""

    if site_match:
        location_name = clean(site_match.group(1))
        street = clean(site_match.group(2))
        suite = clean(site_match.group(3))
        city = clean(site_match.group(4)).title()
        state = clean(site_match.group(5))
        zip_code = clean(site_match.group(6))
    else:
        location_name = ""
        street = ""
        suite = ""
        city = ""
        state = "TX"
        zip_code = ""

    description = clean(description_match.group(1)) if description_match else ""
    scope = clean(scope_match.group(1)) if scope_match else ""
    special_instructions = clean(instructions_match.group(1)) if instructions_match else ""

    job_description = f"""Work Order Description:
{description}

Assignment Scope:
{scope}
"""

    notes_for_techs = f"""Work Order Special Instructions:
{special_instructions}
"""

    return {
        "provider": "The Buckle Inc",
        "customer": "The Buckle Inc",
        "location_name": location_name,
        "street": street,
        "suite": suite,
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": wo_number,
        "wo_number": wo_number,
        "approved_cost": approved_cost,
        "priority": priority,
        "service_date": service_date,
        "service_time": service_time,
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": job_description,
        "notes_for_techs": notes_for_techs,
    }