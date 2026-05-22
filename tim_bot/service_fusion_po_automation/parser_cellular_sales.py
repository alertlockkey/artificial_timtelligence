# parser_cellular_sales.py
import re
from pathlib import Path
from bs4 import BeautifulSoup


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_html_text(file_path: Path) -> str:
    html = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n")


def parse_cellular_sales_po(file_path: Path) -> dict:
    text = extract_html_text(file_path)

    po_match = re.search(r"Purchase Order\s*-\s*(\d+)", text, re.I)
    location_id_match = re.search(r"Location ID:\s*(.+)", text, re.I)
    nte_match = re.search(r"\bNTE\b\s*\n\s*Scheduled.*?\n.*?\n.*?\n\s*([\d,]+\.\d{2})", text, re.DOTALL | re.I)
    scheduled_match = re.search(r"Scheduled\s*Date/Time\s*\n.*?\n.*?\n.*?\n.*?\n(.+?CST)", text, re.DOTALL | re.I)

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

    ivr_match = re.search(
        r"Alternatively, you can use our phone based automated response system.*?Your PIN",
        text,
        re.DOTALL | re.I,
    )

    po_number = po_match.group(1) if po_match else ""
    location_id = clean(location_id_match.group(1)) if location_id_match else ""
    approved_cost = clean(nte_match.group(1)) if nte_match else ""
    service_date = clean(scheduled_match.group(1)) if scheduled_match else ""

    raw_problem = clean(problem_match.group(1)) if problem_match else ""
    ivr_pin = pin_match.group(1) if pin_match else ""

    # Location block:
    # Location ID: ST-BA-TX
    # Bastrop
    # 490 W State Highway 71
    # -
    # Bastrop TX 78602-3731
    location_block_match = re.search(
        r"Location ID:\s*ST-BA-TX\s*\n"
        r"(.+?)\n"
        r"(.+?)\n"
        r"-\n"
        r"(.+?)\s+([A-Z]{2})\s+([\d\-]+)",
        text,
        re.I,
    )

    if location_block_match:
        city_label = clean(location_block_match.group(1))
        street = clean(location_block_match.group(2))
        city = clean(location_block_match.group(3)).title()
        state = clean(location_block_match.group(4))
        zip_code = clean(location_block_match.group(5))
    else:
        city_label = ""
        street = ""
        city = ""
        state = "TX"
        zip_code = ""

    location_name = f"Verizon Wireless {location_id}".strip()

    job_description = f"""Problem Description:
{raw_problem}
"""

    notes_for_techs = f"""Alternatively, you can use our phone based automated response system (IVR) by dialing 516-500-7776, 516-200-3363 to check in upon arrival to the location and to check out upon completion of your visit.

You can also accept/decline the service request using IVR.

Your PIN to access the ServiceChannel Provider mobile app and automated response system: {ivr_pin}
"""

    return {
        "provider": "Cellular Sales",
        "customer": "Cellular Sales",
        "location_name": location_name,
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": po_number,
        "wo_number": po_number,
        "approved_cost": approved_cost,
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