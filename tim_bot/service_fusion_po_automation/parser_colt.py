import re
import fitz
from pathlib import Path


def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_colt_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    wo_match = re.search(r"(WKO-\d+)", text)
    po_match = re.search(r"VENDOR PO #\s*\n?([0-9\-]+)", text)
    cost_match = re.search(r"APPROVED SERVICE COST\s*\n(?:SERVICE DATE\s*\nORDER DATE\s*\n)?(?:WKO-\d+\s*\n)?([0-9]+\.[0-9]{2})", text)
    date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", text)

    location_match = re.search(
        r"Service Location\s*\n(.+?)\s+Location:\s*(\d+)\s*\n(.+?)\s*\n([A-Z ]+),?\s*TX\s*([0-9\-]+)",
        text,
        re.DOTALL,
    )

    manager_match = re.search(
        r"Rebecka Pochop\s+([0-9\-]+)\s+([0-9\-]+)\s+(\S+@\S+)",
        text,
    )

    ivr_match = re.search(r"IVR Pin #\s*\n?([0-9]+)", text)

    job_desc_match = re.search(
        r"•\s*(.+?)\s*Job Description",
        text,
        re.DOTALL,
    )

    best_contact_match = re.search(r"Best Contact:\s*([A-Za-z ]+)", text)
    best_phone_match = re.search(r"Best Contact Phone:\s*([0-9]+)", text)

    customer = ""
    store_number = ""
    street = ""
    city = ""
    zip_code = ""

    if location_match:
        customer = clean_spaces(location_match.group(1))
        store_number = clean_spaces(location_match.group(2))
        street = clean_spaces(location_match.group(3))
        city = clean_spaces(location_match.group(4)).title()
        zip_code = clean_spaces(location_match.group(5))

    scope = clean_spaces(job_desc_match.group(1)) if job_desc_match else ""

    best_contact = clean_spaces(best_contact_match.group(1)) if best_contact_match else ""
    best_phone = clean_spaces(best_phone_match.group(1)) if best_phone_match else ""

    wo_number = wo_match.group(1) if wo_match else ""
    po_number = po_match.group(1) if po_match else ""
    approved_cost = cost_match.group(1) if cost_match else ""
    service_date = date_match.group(1) if date_match else ""
    ivr_pin = ivr_match.group(1) if ivr_match else ""

    manager_phone = manager_match.group(1) if manager_match else ""
    manager_email = manager_match.group(3) if manager_match else ""

    job_description = f"""Service Call - {customer}

Issue:
{scope}

Service Location:
{customer}
{street}
{city}, TX {zip_code}

PO #: {po_number}
WO #: {wo_number}
Approved Service Cost / NTE: ${approved_cost}

Site Contact:
{best_contact} - {best_phone}

WO Manager:
Rebecka Pochop
{manager_phone}
{manager_email}

Instructions:
Always identify yourself as a representative for Colt.
Colt is the customer - store will not pay your bill.
Call WO manager upon arrival and completion.
Do not proceed with additional work without prior approval.
Before and after photos required.
Completion ticket must be stamped/signed before leaving.

IVR:
Call 866-254-9180 upon arrival and departure.
IVR Pin: {ivr_pin}
"""

    notes_for_techs = f"""PO #: {po_number}
WO #: {wo_number}
NTE: ${approved_cost}

Site Contact:
{best_contact} - {best_phone}

IVR Pin: {ivr_pin}
Call 866-254-9180 for check-in/check-out.

Call WO manager upon arrival and completion.
Do not exceed approved amount without authorization.
Before and after photos required.
Get completion ticket signed/stamped before leaving.
"""

    return {
        "customer": "Colt Facility Maintenance",
        "location_name": customer,
        "street": street,
        "suite": "",
        "city": city,
        "state": "TX",
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": wo_number,
        "approved_cost": approved_cost,
        "service_date": service_date,
        "current_status": "Dispatched",
        "assigned_techs": [
            # "Exact Service Fusion Tech Name"
        ],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": job_description,
        "notes_for_techs": notes_for_techs,
    }