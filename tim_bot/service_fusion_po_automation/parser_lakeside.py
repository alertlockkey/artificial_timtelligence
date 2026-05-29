# parser_lakeside.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_location_name(site_code: str) -> str:
    site_code = clean(site_code)

    # Known Lakeside site-name mapping
    if site_code.upper() == "AUS22":
        return "Amazon AUS22"

    return site_code


def parse_lakeside_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    wo_match = re.search(r"Work Order #\s*(\d+)", text, re.I)
    ref_match = re.search(r"Reference #\s*(\S+)", text, re.I)
    nte_match = re.search(r"Affiliate NTE\s*\$?([\d,]+\.\d{2})", text, re.I)

    pm_name_match = re.search(r"Project Manager\s+(.+)", text, re.I)
    pm_phone_match = re.search(r"Project Manager Phone #\s*(.+)", text, re.I)
    pm_email_match = re.search(r"Project Manager Email\s*(\S+@\S+)", text, re.I)

    location_match = re.search(
        r"Work Order Site Address\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(.+?),\s*([A-Za-z]+)\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    scope_match = re.search(
        r"Scope\s*(.+?)\s*Please check in/out",
        text,
        re.DOTALL | re.I,
    )

    notes_match = re.search(
        r"(Please check in/out.+?Call if NTE exceeds amount given)",
        text,
        re.DOTALL | re.I,
    )

    wo_number = wo_match.group(1) if wo_match else ""
    reference_number = ref_match.group(1) if ref_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""

    pm_name = clean(pm_name_match.group(1)) if pm_name_match else ""
    pm_phone = clean(pm_phone_match.group(1)) if pm_phone_match else ""
    pm_email = clean(pm_email_match.group(1)) if pm_email_match else ""

    if location_match:
        site_code = clean(location_match.group(1))
        location_name = normalize_location_name(site_code)
        street = clean(location_match.group(2)).rstrip(".")
        city = clean(location_match.group(3)).title()
        state = clean(location_match.group(4))
        zip_code = clean(location_match.group(5))
    else:
        site_code = ""
        location_name = ""
        street = ""
        city = ""
        state = "Texas"
        zip_code = ""

    scope_text = clean(scope_match.group(1)) if scope_match else ""
    notes_text = clean(notes_match.group(1)) if notes_match else ""

    job_description = scope_text

    notes_for_techs = f"""{notes_text}

Project Manager:
{pm_name}
{pm_phone}
{pm_email}
"""

    return {
        "provider": "Lakeside Project Solutions",
        "customer": "Lakeside Project Solutions",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": wo_number,
        "wo_number": wo_number,
        "reference_number": reference_number,
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