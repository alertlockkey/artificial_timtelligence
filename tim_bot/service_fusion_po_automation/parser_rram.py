# parser_rram.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_rram_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    po_match = re.search(r"PO\s*#-?\s*(\d+)", text, re.I)
    wo_match = re.search(r"WO\s*#:\s*(?:Service Call-)?(\d+)", text, re.I)
    nte_match = re.search(r"NOT TO EXCEED:\s*\$?([\d,]+\.\d{2})", text, re.I)
    priority_match = re.search(r"Priority:\s*(.+)", text, re.I)

    site_match = re.search(r"Site:\s*(.+)", text, re.I)

    address_match = re.search(
        r"Site Address:\s*(.+?)\n"
        r"(.+?)\n"
        r"(#\S+)\n"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    if not address_match:
        address_match = re.search(
            r"Address:\s*(.+?)\n"
            r"(.+?)\n"
            r"(#\S+)\n"
            r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
            text,
            re.DOTALL | re.I,
        )

    scope_match = re.search(
        r"Scope of Work:\s*(.+?)\s*PLEASE INCLUDE COMPLETION PHOTOS",
        text,
        re.DOTALL | re.I,
    )

    ivr_phone_match = re.search(r"Phone:\s*([\d\-]+)", text, re.I)
    ivr_code_match = re.search(r"Enter the 9-digit Code and then #:\s*(\d+)", text, re.I)

    issue_contact_match = re.search(
        r"If issues occur, contact\s*(.+?)\.",
        text,
        re.DOTALL | re.I,
    )

    po_number = po_match.group(1) if po_match else ""
    wo_number = wo_match.group(1) if wo_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    priority = clean(priority_match.group(1)) if priority_match else ""
    location_name = clean(site_match.group(1)) if site_match else ""

    if address_match:
        street = clean(f"{address_match.group(1)} {address_match.group(2)}")
        suite = clean(address_match.group(3))
        city = clean(address_match.group(4)).title()
        state = clean(address_match.group(5))
        zip_code = clean(address_match.group(6))
    else:
        street = ""
        suite = ""
        city = ""
        state = "TX"
        zip_code = ""

    scope_text = clean(scope_match.group(1)) if scope_match else ""
    ivr_phone = clean(ivr_phone_match.group(1)) if ivr_phone_match else ""
    ivr_code = clean(ivr_code_match.group(1)) if ivr_code_match else ""

    issue_contact = clean(issue_contact_match.group(1)) if issue_contact_match else (
        "Alisha VanDenHul @ Office Phone: +1 928 963 3356; "
        "Mobile: +1 928 202 8608; Email: avandenhul@rramservices.com"
    )

    job_description = f"""Scope of Work:
{scope_text}
"""

    notes_for_techs = f"""IMPORTANT!!! You are required to check in/out of this job using an "IVR system" accessed from your phone by using the information below and following the prompts:

Phone: {ivr_phone}
Enter the 9-digit Code and then #: {ivr_code}

NOTE: Your invoice may be rejected if this required process is not performed properly. Contact a RRAM Project Manager for help if required.

If issues occur, contact {issue_contact}.
"""

    return {
        "provider": "RRAM Services",
        "customer": "RRAM Services",
        "location_name": location_name,
        "street": street,
        "suite": suite,
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": wo_number,
        "approved_cost": approved_cost,
        "priority": priority,
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