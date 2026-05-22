# parser_keuper.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_keuper_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    wr_match = re.search(r"Work Task Number:\s*(WR-\d+)", text, re.I)
    building_code_match = re.search(r"Building Code:\s*(.+)", text, re.I)
    address_match = re.search(r"Address:\s*(.+)", text, re.I)
    city_state_zip_match = re.search(
        r"City,\s*State Zip:\s*([^,]+),\s*([A-Z]{2})\s*([\d\-]+)",
        text,
        re.I,
    )
    description_match = re.search(
        r"Work Request Description:\s*(.+?)\s*Comments:",
        text,
        re.DOTALL | re.I,
    )

    po_number = wr_match.group(1) if wr_match else ""
    building_code = clean(building_code_match.group(1)) if building_code_match else ""
    street = clean(address_match.group(1)) if address_match else ""

    if city_state_zip_match:
        city = clean(city_state_zip_match.group(1)).title()
        state = clean(city_state_zip_match.group(2))
        zip_code = clean(city_state_zip_match.group(3))
    else:
        city = ""
        state = "TX"
        zip_code = ""

    scope_text = clean(description_match.group(1)) if description_match else ""

    location_name = f"PNC Bank {building_code}".strip()

    job_description = f"""Work Request Description:
{scope_text}
"""

    notes_for_techs = f"""Service Location:
{location_name}
{street}
{city}, {state} {zip_code}
"""

    return {
        "provider": "Keuper Construction",
        "customer": "Keuper Construction",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": po_number,
        "approved_cost": "",
        "service_date": "",
        "current_status": "Dispatched",
        "assigned_techs": ["Sean Flanagan"],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": job_description,
        "notes_for_techs": notes_for_techs,
    }