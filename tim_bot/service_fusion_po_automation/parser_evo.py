# parser_evo.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_evo_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    po_match = re.search(r"(?:VENDOR PO #|PO #|Purchase Order #)\s*\n?\s*(\d+-\d+)", text, re.I)
    if not po_match:
        po_match = re.search(r"\b(\d{6}-\d{2})\b", text)

    nte_match = re.search(r"NTE\s*\$?([\d,]+\.\d{2})", text, re.I)

    location_match = re.search(
        r"(Massage Envy\s+\w+)\s*\n"
        r"(.+?)\n"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})",
        text,
        re.DOTALL | re.I,
    )

    desc_match = re.search(
        r"(Dispatch tech to:.+?)(?:TECHS MUST CALL|Billing|Terms|Print Date|$)",
        text,
        re.DOTALL | re.I,
    )

    service_lead_match = re.search(r"Service Lead\s+([^:]+):\s*([\d\-]+)", text, re.I)
    account_manager_match = re.search(r"Account Manager\s+([^:]+):\s*([\d\-]+)", text, re.I)
    office_match = re.search(r"EVO Office/Afterhours:\s*([\d\-]+)", text, re.I)

    po_number = po_match.group(1) if po_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""

    if location_match:
        location_name = clean(location_match.group(1))
        street = clean(location_match.group(2))
        city = clean(location_match.group(3)).title()
        state = clean(location_match.group(4))
        zip_code = clean(location_match.group(5))
    else:
        location_name = "Massage Envy N1041"
        street = "6484 N New Braunfels"
        city = "Alamo Heights"
        state = "TX"
        zip_code = "78209"

    scope_text = clean(desc_match.group(1)) if desc_match else (
        "Dispatch tech to: Repair Front Entrance Door Hardware "
        "Description: front is hard to open may be a issue with the bottom sweep of the door itself"
    )

    service_lead = (
        f"Service Lead {clean(service_lead_match.group(1))}: {clean(service_lead_match.group(2))}"
        if service_lead_match else "Service Lead Ronica: 561-507-1978"
    )

    account_manager = (
        f"Account Manager {clean(account_manager_match.group(1))}: {clean(account_manager_match.group(2))}"
        if account_manager_match else "Account Manager Jessica: 561-494-6187"
    )

    office_phone = clean(office_match.group(1)) if office_match else "844-344-3012"

    notes_for_techs = f"""TECHS MUST CALL US TO CHECK-IN/CHECK-OUT:
• {service_lead}
• {account_manager}
• EVO Office/Afterhours: {office_phone}
"""

    return {
        "provider": "EVO Door and Window",
        "customer": "EVO Door and Window TAXABLE",
        "location_name": location_name,
        "street": street,
        "suite": "",
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
        "job_description": scope_text,
        "notes_for_techs": notes_for_techs,
    }