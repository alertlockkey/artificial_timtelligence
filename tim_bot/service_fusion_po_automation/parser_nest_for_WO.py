# parser_nest.py
import re
from pathlib import Path
from pdf_text import extract_text


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()

def clean_multiline(value: str) -> str:
    value = value or ""

    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n\n", value)
    value = re.sub(r"\s*\n\s*", "\n", value)

    # Add blank lines between instruction sentences/sections
    value = re.sub(
        r"(non-payment\.)\s+(Use ISP Connect)",
        r"\1\n\n\2",
        value,
        flags=re.I,
    )

    value = re.sub(
        r"(\d{4}-\d{2}\.)\s+(You will receive)",
        r"\1\n\n\2",
        value,
        flags=re.I,
    )

    return value.strip()

def parse_nest_location(text: str):
    lines = [clean(line) for line in text.splitlines() if clean(line)]

    client_idx = lines.index("Client Details")
    loc_idx = next(i for i, line in enumerate(lines) if line.startswith("Location#:"))
    phone_idx = next(i for i, line in enumerate(lines) if line.startswith("Phone #"))

    client_name = lines[client_idx + 1]
    location_number = re.search(r"Location#:\s*(.+)", lines[loc_idx]).group(1).strip()

    # Everything between Location# and Phone# is location detail/address.
    location_block = lines[loc_idx + 1:phone_idx]

    # Find city/state/zip line.
    city_state_zip_idx = next(
        i for i, line in enumerate(location_block)
        if re.search(r",\s*[A-Z]{2}\s+\d{5}", line)
    )

    city_state_zip = location_block[city_state_zip_idx]
    street = location_block[city_state_zip_idx - 1]

    m = re.search(r"(.+?),\s*([A-Z]{2})\s+(\d{5})", city_state_zip)
    city = m.group(1).title()
    state = m.group(2)
    zip_code = m.group(3)

    # Clean client name for Service Fusion location name
    client_clean = client_name.replace(", Inc.", "").replace("Inc.", "").strip()

    return {
        "client_name": client_name,
        "location_number": location_number,
        "location_name": f"{client_clean} {location_number}",
        "street": street,
        "suite": "",
        "city": city,
        "state": state,
        "zip": zip_code,
    }

def parse_nest_po(pdf_path: Path) -> dict:
    text = extract_text(pdf_path)

    wo_match = re.search(r"WORK ORDER\s*\n?(\d+-\d+)", text, re.I)
    location_number_match = re.search(r"Location#:\s*(\d+)", text, re.I)
    priority_match = re.search(r"Priority:\s*(.+)", text)
    category_match = re.search(r"Category:\s*(.+)", text)
    service_match = re.search(r"Service:\s*(.+)", text)
    schedule_match = re.search(
        r"Schedule Date:\s*(\d{2}/\d{2}/\d{4})\s*([\d:]+\s*[AP]M)",
        text,
        re.I,
    )

    checkin_match = re.search(
        r"Check-In Instructions\s*(.+?)\s*Service Description",
        text,
        re.DOTALL | re.I,
    )

    description_match = re.search(
        r"Service Description\s*(.+?)\s*Signatures",
        text,
        re.DOTALL | re.I,
    )

    # Address block between Location# and Phone #
    # address_match = re.search(
    #     r"Location#:\s*\d+\s*\n"
    #     r"(.+?)\n"
    #     r"(.+?)\n"
    #     r"(.+?)\n"
    #     r"(.+?)\n"
    #     r"([A-Za-z ]+),\s*([A-Z]{2})\s*(\d{5})",
    #     text,
    #     re.DOTALL,
    # )

    client_match = re.search(
        r"Client Details\s*\n(.+?)\n",
        text,
        re.I,
    )

    phone_match = re.search(r"Phone #\s*([\d\-]+)", text)

    wo_number = wo_match.group(1) if wo_match else ""
    location_number = location_number_match.group(1) if location_number_match else ""

    client_name = clean(client_match.group(1)) if client_match else ""
    location_name = client_name

    # if address_match:
    #     location_label_1 = clean(address_match.group(1))
    #     location_label_2 = clean(address_match.group(2))
    #     location_label_3 = clean(address_match.group(3))
    #     street = clean(address_match.group(4))
    #     city = clean(address_match.group(5)).title()
    #     state = clean(address_match.group(6))
    #     zip_code = clean(address_match.group(7))

    #     # Example:
    #     # Mattress Firm
    #     # Bandera Pointe
    #     # In Line
    #     # 11411 Bandera Road
    #     location_name = f"{location_label_1} - {location_label_2}".strip(" -")
    #     suite = location_label_3
    # else:
    #     street = ""
    #     city = ""
    #     state = "TX"
    #     zip_code = ""
    #     suite = ""

    loc = parse_nest_location(text)

    client_name = loc["client_name"]
    location_number = loc["location_number"]
    location_name = loc["location_name"]
    street = loc["street"]
    suite = loc["suite"]
    city = loc["city"]
    state = loc["state"]
    zip_code = loc["zip"]

    priority = clean(priority_match.group(1)) if priority_match else ""
    category = clean(category_match.group(1)) if category_match else ""
    service = clean(service_match.group(1)) if service_match else ""
    schedule_date = schedule_match.group(1) if schedule_match else ""
    schedule_time = schedule_match.group(2) if schedule_match else ""

    site_phone = phone_match.group(1) if phone_match else ""
    checkin_text = clean_multiline(checkin_match.group(1)) if checkin_match else ""
    scope_text = clean(description_match.group(1)) if description_match else ""

    job_description = f"""Issue / Scope:
{scope_text}
"""

    notes_for_techs = f"""{checkin_text}

Instructions:
Checking in/out is required.
Use ISP Connect to obtain Esignature.
Failure to check in/out may result in an admin fee or non-payment.
"""

    return {
        "provider": "NEST",
        "customer": "NEST",
        "location_name": location_name,
        "street": street,
        "suite": suite,
        "city": city,
        "state": state,
        "zip": zip_code,
        "po_number": wo_number,
        "wo_number": wo_number,
        "approved_cost": "",
        "service_date": schedule_date,
        "service_time": schedule_time,
        "current_status": "Dispatched",
        "assigned_techs": [],
        "line_items": [
            "Service Call",
            "Labor 1 Man per hour Standard",
        ],
        "job_description": job_description,
        "notes_for_techs": notes_for_techs,
    }