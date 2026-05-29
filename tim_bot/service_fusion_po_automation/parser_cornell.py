# parser_cornell.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_location_name(raw: str) -> str:
    # FIRESTONE # 654795 -> FIRESTONE 654795
    return clean(raw).replace("#", "").strip()


def parse_cornell_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    vendor_po_match = re.search(
        r"VENDOR PO #\s*\n(?:Job #\s*\n)?(?:.*?\n)*?(\d{6}-\d{2})",
        text,
        re.I,
    )

    if not vendor_po_match:
        vendor_po_match = re.search(r"\b(\d{6}-\d{2})\b", text)

    client_po_match = re.search(r"Client PO #\s*(WO\d+)", text, re.I)
    if not client_po_match:
        client_po_match = re.search(r"\b(WO\d+)\b", text, re.I)

    nte_match = re.search(r"NTE\s*\$?([\d,]+\.\d{2})", text, re.I)
    service_date_match = re.search(
        r"Service Date\s*(\d{1,2}/\d{1,2}/\d{2}\s+\d{1,2}:\d{2}\s*[AP]M)",
        text,
        re.I,
    )

    location_match = re.search(
        r"SERVICE LOCATION\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(.+?),\s*([A-Z]{2})\s*(\d{5})(?:-\d{4})?",
        text,
        re.DOTALL | re.I,
    )

    description_match = re.search(
        r"SERVICE DESCRIPTION\s*(.+?)\s*(?:DISPATCH COST|Store Manager|$)",
        text,
        re.DOTALL | re.I,
    )

    sc_ivr_phone_match = re.search(r"IVR #\s*-\s*([\d\-]+)", text, re.I)
    sc_ivr_pin_match = re.search(r"IVR\s*PIN\s*-\s*(\d+)", text, re.I)

    fallback_ivr_match = re.search(
        r"If not a Service Channel work order,\s*IVR #\s*-\s*([\d\-]+).*?IVR PIN\s*-\s*Use Vendor PO",
        text,
        re.DOTALL | re.I,
    )

    vendor_po = vendor_po_match.group(1) if vendor_po_match else ""
    vendor_po_base = vendor_po.split("-")[0] if vendor_po else ""

    client_po = client_po_match.group(1) if client_po_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    service_date = clean(service_date_match.group(1)) if service_date_match else ""

    if location_match:
        location_name = normalize_location_name(location_match.group(1))
        street = clean(location_match.group(2))
        city = clean(location_match.group(3)).title()
        state = clean(location_match.group(4))
        zip_code = clean(location_match.group(5))
    else:
        location_name = ""
        street = ""
        city = ""
        state = "TX"
        zip_code = ""

    scope_text = clean(description_match.group(1)) if description_match else ""

    sc_ivr_phone = clean(sc_ivr_phone_match.group(1)) if sc_ivr_phone_match else "516-500-7776"
    sc_ivr_pin = clean(sc_ivr_pin_match.group(1)) if sc_ivr_pin_match else ""
    fallback_ivr_phone = clean(fallback_ivr_match.group(1)) if fallback_ivr_match else "833-330-2306"

    notes_for_techs = f"""MUST USE SERVICE CHANNEL APP AS FIRST IVR ATTEMPT
IF UNAVAILABLE- IVR # - {sc_ivr_phone}
IVR PIN - {sc_ivr_pin}
USE ANY PHONE
WO/TRACKING # - {client_po}

If not a Service Channel work order, IVR # - {fallback_ivr_phone}
IVR PIN - {vendor_po_base}

PLEASE CALL 800-882-6773 EXT 1 to speak with a Service Coordinator if an NTE increase is needed or if you have any issues with the IVR system.
"""

    return {
        "provider": "Cornell Storefront Systems",
        "customer": "Cornell Storefront Systems",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": vendor_po,
        "wo_number": client_po,
        "client_po": client_po,
        "approved_cost": approved_cost,
        "service_date": service_date,
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": scope_text,
        "notes_for_techs": notes_for_techs,
    }