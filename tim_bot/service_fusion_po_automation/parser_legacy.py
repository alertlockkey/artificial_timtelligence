# parser_legacy.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_legacy_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    wo_match = re.search(r"(\d{6}-\d{2})", text)
    service_date_match = re.search(
        r"Service Date\s+(\d{1,2}/\d{1,2}/\d{2})", text
    )

    location_match = re.search(
        r"Phone #\s+\d{3}-\d{3}-\d{4}\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"([A-Z ]+),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL,
    )

    service_location_id_match = re.search(r"Service Location\s+(\d+)", text)

    description_match = re.search(
        r"Service Description\s*(.+?)\s*Incurred",
        text,
        re.DOTALL,
    )

    nte_match = re.search(r"Total NTE\s*\$?([\d,]+\.\d{2})", text)

    ivr_pin_match = re.search(
    r"Service Location\s*\n.*?\n(\d{6,})\s*\nIVR Pin #",
    text,
    re.DOTALL | re.I,
    )

    if not ivr_pin_match:
        ivr_pin_match = re.search(
            r"(\d{6,})\s*\nIVR Pin #",
            text,
            re.I,
        )
    ivr_phone_match = re.search(
    r"(\d{3}-\d{3}-\d{4})\s*\nIVR Phone #",
    text,
    re.I,
    )

    updates_email_match = re.search(r"updates and proposals to\s+(\S+@\S+)", text, re.I)
    invoice_email_match = re.search(r"Email \(preferred method\):\s*(\S+@\S+)", text)

    location_name = clean(location_match.group(1)) if location_match else ""
    street = clean(location_match.group(2)) if location_match else ""

    # Legacy sometimes has an extra center/building line before city/state/zip.
    location_extra = clean(location_match.group(3)) if location_match else ""
    city = clean(location_match.group(4)).title() if location_match else ""
    state = clean(location_match.group(5)) if location_match else "TX"
    zip_code = clean(location_match.group(6)) if location_match else ""

    wo_number = wo_match.group(1) if wo_match else ""
    service_date = service_date_match.group(1) if service_date_match else ""
    service_location_id = service_location_id_match.group(1) if service_location_id_match else ""
    nte = clean(nte_match.group(1)) if nte_match else ""

    ivr_pin = ivr_pin_match.group(1) if ivr_pin_match else ""
    ivr_phone = ivr_phone_match.group(1) if ivr_phone_match else "866-254-9430"

    updates_email = clean(updates_email_match.group(1)) if updates_email_match else "TeamG@legacyfms.com"
    invoice_email = clean(invoice_email_match.group(1)) if invoice_email_match else "Invoicing@legacyfms.com"

    scope_text = clean(description_match.group(1)) if description_match else ""

    job_description = f"""Issue / Scope:
{scope_text}
"""

    notes_for_techs = f"""IVR:
Phone: {ivr_phone}
Pin: {ivr_pin}

Instructions:
Checking in/out is required upon arrival and departure.
Call Legacy from site for any increase needed above issued NTE.
Do not proceed above NTE without Legacy approval.
Photos and incurred costs are required when quoting further work.
Pricing can only be discussed with a Legacy representative.
Do not leave invoices or paperwork on site.
A signed work order is required for payment.
"""

    return {
        "provider": "Legacy Group Enterprises Inc",
        "customer": "Legacy Group Enterprises Inc",
        "location_name": location_name,
        "street": street,
        "suite": location_extra,
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": wo_number,
        "wo_number": wo_number,
        "approved_cost": nte,
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