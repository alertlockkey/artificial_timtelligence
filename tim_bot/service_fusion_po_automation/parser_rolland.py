# parser_rolland.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_rolland_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    po_match = re.search(r"#?\s*PO\s*(\d+)", text, re.I)
    nte_match = re.search(r"MUST CALL IF EXCEEDING NTE\s*\$?([\d,]+\.\d{2})", text, re.I)

    location_match = re.search(
        r"(Verizon\s*-\s*.+?)\s*\n"
        r"(.+?)\s+SUITE\s*\n?"
        r"(\d+)\s*\n"
        r"([A-Z ]+)\s+([A-Z]{2})\s+(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    dispatch_match = re.search(
        r"Dispatch Instructions:\s*(.+?)\s*Customer Request:",
        text,
        re.DOTALL | re.I,
    )

    checkout_match = re.search(
        r"UPON DEPARTURE \(IVR CHECKOUT\)\s*(.+?)\s*FOR PROMPT PAYMENT",
        text,
        re.DOTALL | re.I,
    )

    po_number = po_match.group(1) if po_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""

    if location_match:
        location_name = clean(location_match.group(1))
        street = clean(location_match.group(2))
        suite = f"STE {clean(location_match.group(3))}"
        city = clean(location_match.group(4)).title()
        state = clean(location_match.group(5))
        zip_code = clean(location_match.group(6))
    else:
        location_name = ""
        street = ""
        suite = ""
        city = ""
        state = "TX"
        zip_code = ""

    dispatch_text = clean(dispatch_match.group(1)) if dispatch_match else ""
    checkout_text = checkout_match.group(1).strip() if checkout_match else ""
    checkout_text = re.sub(r"\n\s*\n", "\n\n", checkout_text)  # normalize spacing
    checkout_text = re.sub(r"\s*\n\s*", "\n", checkout_text)  # trim lines

    job_description = f"""Dispatch Instructions:
{dispatch_text}
"""

    notes_for_techs = f"""UPON DEPARTURE (IVR CHECKOUT)
{checkout_text}
"""

    return {
        "provider": "Rolland",
        "customer": "Rolland",
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
        "notes_for_techs": f"""UPON DEPARTURE (IVR CHECKOUT)

            {checkout_text}
            """
    }