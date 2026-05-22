# parser_true_source.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_true_source_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    wo_match = re.search(r"Work Order\s+(WO-\d+)", text, re.I)
    ts_pin_match = re.search(r"WO-\d+\s+PIN\s+(\d+)", text, re.I)

    store_number_match = re.search(r"Site Store Number:\s*(.+)", text, re.I)
    priority_match = re.search(r"Work Order Priority:\s*(.+)", text, re.I)
    skill_type_match = re.search(r"Skill Type:\s*(.+)", text, re.I)
    nte_match = re.search(r"Not to Exceed Amount:\s*\$\s*([\d,]+\.\d{2})", text, re.I)

    wo_number = wo_match.group(1) if wo_match else ""
    ts_pin = ts_pin_match.group(1) if ts_pin_match else ""
    store_number = clean(store_number_match.group(1)) if store_number_match else ""
    priority = clean(priority_match.group(1)) if priority_match else ""
    skill_type = clean(skill_type_match.group(1)) if skill_type_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""

    address_match = re.search(
        r"Site Address:\s*(.+?),\s*([^,]+),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.I,
    )

    if address_match:
        street = clean(address_match.group(1))
        city = clean(address_match.group(2)).title()
        state = clean(address_match.group(3))
        zip_code = clean(address_match.group(4))
    else:
        street = ""
        city = ""
        state = "TX"
        zip_code = ""

    description_match = re.search(
        r"Description of Work:\s*(.+?)\s*This work has been sent",
        text,
        re.DOTALL | re.I,
    )

    raw_description = clean(description_match.group(1)) if description_match else ""

    customer_ivr_match = re.search(
        r"YOU ARE REQUIRED.*?PHONE NUMBER:\s*([\d\-]+)\s+PIN:\s*(\d+)\s+CUST PO:\s*(\d+)",
        raw_description,
        re.I,
    )

    if customer_ivr_match:
        customer_ivr_phone = clean(customer_ivr_match.group(1))
        customer_ivr_pin = clean(customer_ivr_match.group(2))
        customer_po = clean(customer_ivr_match.group(3))
    else:
        customer_ivr_phone = ""
        customer_ivr_pin = ""
        customer_po = ""

    # Remove IVR boilerplate from job scope
    scope_text = re.sub(
        r"\*?\*?\s*YOU ARE REQUIRED.*?CUST PO:\s*\d+\s*\*?\*?\s*/?",
        "",
        raw_description,
        flags=re.I,
    )

    # Remove duplicated skill type from beginning if present
    if skill_type:
        scope_text = re.sub(
            rf"^{re.escape(skill_type)},?\s*",
            "",
            scope_text,
            flags=re.I,
        )

    scope_text = clean(scope_text).lstrip("/").strip()

    location_name = f"T-MOBILE {store_number}".strip()

    job_description = f"""{skill_type}, {scope_text}
"""

    notes_for_techs = f"""YOU ARE REQUIRED TO UTILIZE THE IVR TO CHECK IN AND OUT, FAILURE TO DO SO MAY RESULT IN NONPAYMENT OF SERVICES BILLED.

PHONE NUMBER: {customer_ivr_phone}
PIN: {customer_ivr_pin}
CUST PO: {customer_po}

True Source IVR also required, use TS affiliate app OR call (877) 287-0370
{wo_number}
PIN {ts_pin}
"""

    return {
        "provider": "True Source LLC",
        "customer": "True Source LLC",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": f"{wo_number.replace('WO-', '')}---1" if wo_number else "",
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