# parser_smile_doctors.py
import re
from pathlib import Path
from bs4 import BeautifulSoup


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_html_text(file_path: Path) -> str:
    html = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n")


def parse_smile_doctors_po(file_path: Path) -> dict:
    text = extract_html_text(file_path)

    po_match = re.search(r"Purchase Order\s*-\s*(\d+)", text, re.I)
    location_id_match = re.search(r"Location ID:\s*([A-Z0-9\-]+)", text, re.I)

    problem_match = re.search(
        r"Problem Description:\s*(.+?)\s*Request Created By",
        text,
        re.DOTALL | re.I,
    )

    pin_match = re.search(
        r"Your PIN to access.*?:\s*(\d+)",
        text,
        re.I,
    )

    nte_match = re.search(
        r"\bNTE\b.*?\n\s*([\d,]+\.\d{2})",
        text,
        re.DOTALL | re.I,
    )

    scheduled_match = re.search(
        r"Scheduled\s*Date/Time.*?\n\s*(May|June|July|August|September|October|November|December|January|February|March|April)\s+\d{1,2},\s+\d{4}\s+[\d:]+\s+CST",
        text,
        re.DOTALL | re.I,
    )

    location_block_match = re.search(
        r"Location ID:\s*([A-Z0-9\-]+)\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"(.+?)\s+([A-Z]{2})\s+([\d\-]+)",
        text,
        re.I,
    )

    po_number = po_match.group(1) if po_match else ""
    location_id = clean(location_id_match.group(1)) if location_id_match else ""
    raw_problem = clean(problem_match.group(1)) if problem_match else ""
    ivr_pin = pin_match.group(1) if pin_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""

    if location_block_match:
        city_label = clean(location_block_match.group(2))
        street = clean(location_block_match.group(3))
        suite = clean(location_block_match.group(4)).replace("Ste.", "Ste")
        city = clean(location_block_match.group(5)).title()
        state = clean(location_block_match.group(6))
        zip_code = clean(location_block_match.group(7))
    else:
        city_label = ""
        street = ""
        suite = ""
        city = ""
        state = "TX"
        zip_code = ""

    customer = f"Smile Doctor {city}".strip()
    location_name = f"Smile Doctors {location_id}".strip()

    job_description = f"""Problem Description:
{raw_problem}
"""

    notes_for_techs = f"""Use our phone based automated response system (IVR) by dialing 516-500-7776, 516-200-3363 to check in upon arrival to the location and to check out upon completion of your visit.

You can also accept/decline the service request using IVR.

Your PIN to access the ServiceChannel Provider mobile app and automated response system: {ivr_pin}
"""

    return {
        "provider": "Smile Doctors",
        "customer": customer,
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
        "notes_for_techs": notes_for_techs,
    }