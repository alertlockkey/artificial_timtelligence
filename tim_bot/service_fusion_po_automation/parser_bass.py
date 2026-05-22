# parser_bass.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def format_location_name(raw: str) -> str:
    raw = clean(raw)
    # H&M#00363 -> H&M #00363
    return re.sub(r"#\s*", " #", raw)


def clean_instruction_block(value: str) -> str:
    value = value or ""
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s*\n\s*", " ", value)
    value = re.sub(r"(\d+\.)", r"\n\1", value)
    value = re.sub(r"MANDATORY", r"\nMANDATORY", value)
    return value.strip()


def parse_bass_address(text: str):
    # Handles:
    # H&M#00363
    # San Antonio, TX 78256
    # 15900 La Cantera PKWY
    # H&M#00363
    m = re.search(
        r"\n([A-Z0-9&'\- ]+#\s*\w+)\s*\n"
        r"([A-Za-z ]+),\s*([A-Z]{2})\s*(\d{5})\s*\n"
        r"(.+?)\s*\n"
        r"\1",
        text,
        re.I,
    )

    if not m:
        return "", "", "", "TX", ""

    location_name = format_location_name(m.group(1))
    city = clean(m.group(2)).title()
    state = clean(m.group(3))
    zip_code = clean(m.group(4))
    street = clean(m.group(5))

    return location_name, street, city, state, zip_code


def parse_bass_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    bass_number_match = re.search(r"Bass Number\s+(\d+)", text, re.I)
    job_desc_match = re.search(r"Job Description:\s*(.+)", text, re.I)
    nte_match = re.search(r"Grand Total NTE Limit:\s*\$?([\d,]+\.\d{2})", text, re.I)

    expected_match = re.search(
        r"Expected Date of Service:\s*(\d{1,2}/\d{1,2}/\d{4})\s+by\s+([\d:]+\s*[AP]M)",
        text,
        re.I,
    )

    sc_pin_match = re.search(r"Service Channel Pin Code\s+(\d+)", text, re.I)
    tracking_match = re.search(r"tracking number\s+(\d+)", text, re.I)

    bass_contact_match = re.search(
        r"Bass Security at\s*(1-\d{3}-\d{3}-\d{4})\s*ext\.?\s*(\d+)",
        text,
        re.I,
    )

    photos_email_match = re.search(r"For photos, email\s*(\S+@\S+)", text, re.I)
    invoice_email_match = re.search(r"invoice to\s*(\S+@\S+)", text, re.I)

    location_name, street, city, state, zip_code = parse_bass_address(text)

    bass_number = bass_number_match.group(1) if bass_number_match else ""
    job_description_text = clean(job_desc_match.group(1)) if job_desc_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""

    service_date = expected_match.group(1) if expected_match else ""
    service_time = expected_match.group(2) if expected_match else ""

    sc_pin = sc_pin_match.group(1) if sc_pin_match else ""
    tracking_number = tracking_match.group(1) if tracking_match else ""

    bass_phone = bass_contact_match.group(1) if bass_contact_match else "1-877-818-5989"
    bass_ext = bass_contact_match.group(2) if bass_contact_match else ""

    photos_email = clean(photos_email_match.group(1)) if photos_email_match else ""
    invoice_email = clean(invoice_email_match.group(1)) if invoice_email_match else "nationalinvoices@bass-security.com"

    job_description = f"""Issue / Scope:
{job_description_text}
"""

    notes_for_techs = f"""MANDATORY Check-In Procedures
1. DOWNLOAD the Service Channel (SC) Provider Mobile App.
2. Upon arrival on site and PRIOR to entering the site enter the Service Channel Pin Code {sc_pin} in the SC App or by calling SC at 1-516-500-7776.
3. Enter the tracking number {tracking_number} and select CHECK IN.
4. Call Bass Security at {bass_phone} ext. {bass_ext} to CHECK IN prior to starting any work.
5. Before PHOTOS are required - Select Media on the GPS App and follow the instructions.
6. Any technical issues and you must call Bass Security immediately before beginning work {bass_phone} ext. {bass_ext}.

MANDATORY Check-out Procedures
1. Once you have completed the current scope of work, cleaned up your work area, loaded your truck, and finalized the Work Order Completion Form, you MUST call Bass Security at {bass_phone} ext. {bass_ext} with ALL completion details.
2. PRIOR to leaving the site, enter the Service Channel Pin Code {sc_pin} and tracking number {tracking_number} in the SC App or by calling SC at 1-516-500-7776.
3. After PHOTOS are required - Select Media on the GPS App and follow the instructions.
4. Select CHECK OUT, enter the work order status, a brief description on the work summary screen, and Select DONE.
5. Any technical issues and you must call Bass Security immediately before beginning work {bass_phone} ext. {bass_ext}.
"""

    return {
        "provider": "Bass Security",
        "customer": "Bass Security",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": bass_number,
        "wo_number": bass_number,
        "approved_cost": approved_cost,
        "service_date": service_date,
        "service_time": service_time,
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": job_description,
        "notes_for_techs": notes_for_techs,
    }