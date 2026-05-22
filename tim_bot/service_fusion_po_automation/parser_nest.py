# parser_nest.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def clean_client_name(value: str) -> str:
    value = clean(value)
    value = re.sub(r",?\s*Inc\.?$", "", value, flags=re.I)
    return value.strip()


def parse_nest_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    wo_match = re.search(r"Work Order #\s*([\d\-]+)", text, re.I)
    schedule_match = re.search(r"Schedule Date:\s*(\d{2}/\d{2}/\d{4})", text, re.I)
    priority_match = re.search(r"Priority:\s*(.+)", text)
    category_match = re.search(r"Category:\s*(.+)", text)
    service_match = re.search(r"Service:\s*(.+)", text)
    nte_match = re.search(r"Verification Sheet\s*\n?\$?([\d,]+(?:\.\d{2})?)", text, re.I)

    location_match = re.search(
        r"Service Location Details\s*\n"
        r"(.+?)\s*#\s*(\d+)\s*\n"
        r"(?:.+?\n)?"  # optional secondary location line, example: Sheplers
        r"(.+?)\n"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})\s*\n"
        r"Phone #\s*([\d\-]+)",
        text,
        re.DOTALL | re.I,
    )

    description_match = re.search(
        r"Service Description\s*(.+?)\s*This will not be accepted",
        text,
        re.DOTALL | re.I,
    )

    wo_number = wo_match.group(1) if wo_match else ""
    service_date = schedule_match.group(1) if schedule_match else ""
    priority = clean(priority_match.group(1)) if priority_match else ""
    category = clean(category_match.group(1)) if category_match else ""
    service = clean(service_match.group(1)) if service_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""

    if location_match:
        client_raw = clean(location_match.group(1))
        location_number = clean(location_match.group(2))
        street = clean(location_match.group(3))
        city = clean(location_match.group(4)).title()
        state = clean(location_match.group(5))
        zip_code = clean(location_match.group(6))
        site_phone = clean(location_match.group(7))
    else:
        client_raw = ""
        location_number = ""
        street = ""
        city = ""
        state = "TX"
        zip_code = ""
        site_phone = ""

    client_name = clean_client_name(client_raw)
    location_name = f"{client_name} {location_number}".strip()
    scope_text = clean(description_match.group(1)) if description_match else ""

    checkin_text = f"""Checking In/Out is REQUIRED. Failure to do so may result in an admin fee or non-payment.

Use ISP Connect to TEXT message and check in: Text #856-452-7719 and include {wo_number}.

You will receive a response with a link to check in/out. (If you must dial in, call 877-374-2054 and enter {wo_number})"""

    job_description = f"""Issue / Scope:
{scope_text}
"""

    notes_for_techs = f"""Check-In / Check-Out:
{checkin_text}

Instructions:
Use ISP Connect to obtain Esignature.
Do not discuss pricing with location personnel.
Contact NEST before proceeding if additional funds are needed.
Any expenses above the NTE without prior approval will not be paid.
"""

    return {
        "provider": "NEST",
        "customer": "NEST",
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