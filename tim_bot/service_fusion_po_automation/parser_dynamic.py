# parser_dynamic.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_dynamic_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    po_number = re.search(r"(PO\d+)", text)
    issued_date = re.search(r"Date Issued\s*\n?(PO\d+\s*)?(\d{2}/\d{2}/\d{4})", text)
    service_manager = re.search(r"Service Manager\s*:\s*(.+)", text)
    manager_email = re.search(r"Email\s*:\s*\n?(\S+@\S+)", text)
    manager_phone = re.search(r"Phone\s*:\s*([+\d]+)", text)

    response_by = re.search(r"Response by Date\s*:\s*\n?(\d{2}/\d{2}/\d{4})", text)
    complete_by = re.search(r"Complete by Date\s*:\s*\n?(\d{2}/\d{2}/\d{4})", text)

    ivr_pin = re.search(r"pin#\s*(\d+)", text, re.I)
    customer_ivr = re.search(r"Customer IVR#\s*:?\s*(\d+)", text)

    address_block = re.search(
        r"Address\s*:\s*\n(.+?)\n(.+?)\n([A-Za-z ]+)\s+([A-Z]{2})\s+([\d\-]+)",
        text,
        re.DOTALL,
    )

    scope = re.search(
        r"Scope of Work\s*(.+?)\s*Site Requirements",
        text,
        re.DOTALL,
    )

    site_requirements = re.search(
        r"Site Requirements\s*:(.+?)\s*LINE ITEMS",
        text,
        re.DOTALL,
    )

    total = re.search(r"Grand\s*Total\s*\$?([\d,]+\.\d{2})", text)

    location_name = clean(address_block.group(1)) if address_block else ""
    street = clean(address_block.group(2)) if address_block else ""
    city = clean(address_block.group(3)).title() if address_block else ""
    state = clean(address_block.group(4)) if address_block else "TX"
    zip_code = clean(address_block.group(5)) if address_block else ""

    po_number = po_number.group(1) if po_number else ""
    manager_name = clean(service_manager.group(1)) if service_manager else ""
    email = clean(manager_email.group(1)) if manager_email else ""
    phone = clean(manager_phone.group(1)) if manager_phone else ""
    nte = clean(total.group(1)) if total else ""

    scope_text = clean(scope.group(1)) if scope else ""
    req_text = clean(site_requirements.group(1)) if site_requirements else ""

    job_description = f"""Issue / Scope:
{scope_text}

Service Manager:
{manager_name}
{phone}
{email}

"""

    notes_for_techs = f"""IVR:
Phone: 516-500-7776
Pin: {ivr_pin.group(1) if ivr_pin else ""}
Customer IVR #: {customer_ivr.group(1) if customer_ivr else ""}

Instructions:
Technician photos and store sign off required.
Check in and out using IVR or Service Channel app.
Only complete work outlined in the PO.
Call requestor before leaving site with update.
Call for approval before exceeding NTE.

Requirements:
{req_text}
"""

    return {
        "provider": "Dynamic Facility Services",
        "customer": "Dynamic Facility Services",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": "",
        "approved_cost": nte,
        "service_date": complete_by.group(1) if complete_by else "",
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": job_description,
        "notes_for_techs": notes_for_techs,
    }