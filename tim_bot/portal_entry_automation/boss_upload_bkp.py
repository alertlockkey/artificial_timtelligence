# This script edits an invoice from one that is already entered.
# Resume testing with a new BOSS invoice.


import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()

BOSS_USERNAME = os.getenv("BOSS_USERNAME")
BOSS_PASSWORD = os.getenv("BOSS_PASSWORD")
DROPBOX_2015 = Path(os.getenv("DROPBOX_2015"))

BOSS_URL = "https://boss.facilit.fm/Vendor?c=boss"


def parse_boss_invoice_name(file: Path):
    pattern = re.compile(
        r"INV Boss Facility WO# (?P<wo_no>.+?) INV# (?P<inv_no>.+?)\.pdf$",
        re.I,
    )
    match = pattern.match(file.name)
    if not match:
        raise ValueError(f"Invalid Boss invoice filename: {file.name}")

    return match.group("wo_no").strip(), match.group("inv_no").strip()


def click_dx_button(page, label: str, timeout: int = 10000):
    """Click a DevExtreme button by its visible label."""
    button = page.get_by_role("button", name=label).first
    button.wait_for(state="visible", timeout=timeout)
    button.click()


def click_dx_button_allow_new_tab(page, label: str, timeout: int = 10000):
    """
    Click a DevExtreme button that may or may not open a new tab/window.
    Returns the page that should be used for the next step.
    """
    try:
        with page.context.expect_page(timeout=5000) as new_page_info:
            click_dx_button(page, label, timeout=timeout)

        new_page = new_page_info.value
        new_page.wait_for_load_state("domcontentloaded")
        return new_page

    except PlaywrightTimeoutError:
        return page


def fill_dx_input(page, selector: str, value):
    """Fill DevExtreme text/number inputs and blur so the widget keeps the value."""
    field = page.locator(selector).first
    field.wait_for(state="visible", timeout=10000)
    field.click()
    field.press("Control+A")
    field.press("Backspace")
    field.type(str(value), delay=50)
    field.press("Tab")


def normalize_date_mmddyy(value) -> str:
    """
    Normalize dates to MM/DD/YY for Boss, so values like 05/20/2026
    and 05/20/26 compare as equal.
    """
    raw = str(value or "").strip()

    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%m/%d/%y")
        except ValueError:
            pass

    parts = raw.split("/")
    if len(parts) == 3:
        month, day, year = parts
        return f"{month.zfill(2)}/{day.zfill(2)}/{year[-2:]}"

    return raw


def select_po_from_embedded_grid(page, wo_no: str):
    """
    Boss uses a DevExtreme embedded grid for PO/WO selection.
    This keeps the working flow:
      1. open dropdown
      2. type WO into the Embedded PO Grid filter input
      3. hover the first filtered result row to activate/highlight it
      4. click Next
    """
    # Wait for dropdown button
    page.wait_for_selector(".dx-dropdowneditor-button", timeout=10000)

    # Click dropdown to open the Embedded PO Grid
    page.locator(".dx-dropdowneditor-button").first.click()

    # Wait for filter input inside grid
    filter_selector = "#Embedded-PO-Grid input.dx-texteditor-input"
    page.wait_for_selector(filter_selector, timeout=10000)

    # Enter WO# into filter row
    filter_input = page.locator(filter_selector).first
    filter_input.click()
    filter_input.press("Control+A")
    filter_input.press("Backspace")
    filter_input.type(str(wo_no), delay=75)

    # Wait briefly for Boss to filter and display the matching PO row.
    page.wait_for_timeout(750)

    # Hover over the first option/row that contains the WO#.
    # Manual testing showed that hovering/highlighting this row lets the page continue correctly.
    po_row = page.locator(
        "#Embedded-PO-Grid tr.dx-data-row",
        has_text=str(wo_no),
    ).first
    po_row.wait_for(state="visible", timeout=10000)
    po_row.hover()
    po_row.click()

    page.wait_for_timeout(500)

    # Click Next using the step-specific selector
    step1_next = page.locator("#Step1Next > div").first
    step1_next.wait_for(state="visible", timeout=10000)
    step1_next.click()


def wait_for_invoice_line_items(page):
    """Wait until the invoice line item form is ready."""
    page.wait_for_selector("input#Invnum", timeout=15000)
    page.wait_for_selector("input#LineItems_0__Quantity", timeout=15000)
    page.wait_for_selector("input#LineItems_0__UnitPrice", timeout=15000)
    page.wait_for_selector("input#LineItems_3__UnitPrice", timeout=15000)
    page.wait_for_selector("input#LineItems_4__UnitPrice", timeout=15000)
    page.wait_for_selector("input#Invdate", timeout=15000)



def extract_labor_description_from_invoice(invoice_pdf: Path) -> str:
    """
    Extract the Labor description from the Boss invoice PDF.

    Expected invoice text shape:
      ... DESCRIPTION QTY RATE AMOUNT
      Service Calls Extended Travel ...
      Material ...
      Labor 1 Man per hour Standard ...
      2 95.00 190.00
      SUBTOTAL ...
    """
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
        except Exception:
            return ""

    try:
        reader = PdfReader(str(invoice_pdf))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""

    match = re.search(
        r"(Labor\s+1\s+Man\s+per\s+hour\s+Standard.*?)(?:\n\s*\d+\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}|\s+SUBTOTAL)",
        text,
        re.I | re.S,
    )
    if not match:
        return ""

    return re.sub(r"\s+", " ", match.group(1)).strip()


def find_boss_signoff_pdf(invoice_pdf: Path, wo_no: str, inv_no: str) -> Path:
    """Find the matching WO Boss signoff PDF in the same folder as the invoice."""
    candidates = [
        invoice_pdf.with_name(f"WO Boss Facility WO# {wo_no} INV# {inv_no}.pdf"),
        invoice_pdf.with_name(invoice_pdf.name.replace("INV Boss Facility", "WO Boss Facility", 1)),
        DROPBOX_2015 / f"WO Boss Facility WO# {wo_no} INV# {inv_no}.pdf",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Could not find matching Boss signoff PDF for WO {wo_no}, INV {inv_no}"
    )


def find_boss_photos(base_folder: Path) -> list[Path]:
    """Find boss photos in the 2015 folder, e.g. boss1.jpg, boss2.jpg, etc."""
    photos = []
    for pattern in ("boss*.jpg", "boss*.jpeg", "boss*.png"):
        photos.extend(base_folder.glob(pattern))

    def photo_sort_key(path: Path):
        match = re.search(r"boss(\d+)", path.stem, re.I)
        return int(match.group(1)) if match else 9999

    return sorted(set(photos), key=photo_sort_key)


def click_selector(page, selector: str, timeout: int = 15000):
    locator = page.locator(selector).first
    locator.wait_for(state="visible", timeout=timeout)
    locator.click()
    return locator


def upload_boss_document(page, open_button_selector: str, comment_selector: str, comment: str, file_path: Path):
    """
    Upload one document from the final Boss invoice screen.

    The modal IDs in Boss can be dynamic, so this uses the user-provided selectors first.
    """
    click_selector(page, open_button_selector)
    page.wait_for_timeout(750)

    fill_dx_input(page, comment_selector, comment)

    file_button_selector = (
        "#DocumentFileUploader > div > div > div > "
        "div.dx-fileuploader-input-wrapper > "
        "div.dx-widget.dx-button.dx-button-mode-contained.dx-button-normal."
        "dx-button-has-text.dx-fileuploader-button > div"
    )

    with page.expect_file_chooser(timeout=15000) as file_chooser_info:
        click_selector(page, file_button_selector)

    file_chooser_info.value.set_files(str(file_path))
    page.wait_for_timeout(1000)

    save_button_selector = (
        "body > div.dx-overlay-wrapper.dx-datagrid-edit-popup.dx-popup-wrapper."
        "dx-overlay-shader > div > div.dx-toolbar.dx-widget."
        "dx-visibility-change-handler.dx-collection.dx-popup-bottom > div > "
        "div.dx-toolbar-after > div:nth-child(1) > div > div > div"
    )
    click_selector(page, save_button_selector)
    page.wait_for_timeout(1500)


def upload_boss_photo(page, photo_path: Path):
    """Upload a single Boss photo on the final invoice screen."""
    photo_open_selector = (
        "#dx-a21a1ed2-b33b-ab64-cb7e-9b047553d7e4 > div > "
        "div.dx-toolbar-after > div:nth-child(1) > div > div > div"
    )

    click_selector(page, photo_open_selector)
    page.wait_for_timeout(750)

    # Type dropdown
    type_selector = "#dx_dx-7a0d8928-467d-e332-2265-40529ee6a771_Type"
    click_selector(page, type_selector)
    page.wait_for_timeout(500)

    # Photos option
    photos_option_selector = (
        "#dx-b5a34e41-683e-2ead-d307-99c99509e823 > "
        "div.dx-scrollable-wrapper > div > div.dx-scrollable-content > "
        "div.dx-scrollview-content > div.dx-item.dx-list-item.dx-state-hover > div"
    )
    try:
        click_selector(page, photos_option_selector, timeout=3000)
    except PlaywrightTimeoutError:
        page.get_by_text("Photos", exact=True).first.click()

    # Comment
    comment_selector = "#dx_dx-7a0d8928-467d-e332-2265-40529ee6a771_Comment"
    fill_dx_input(page, comment_selector, "photo")

    file_button_selector = (
        "#DocumentFileUploader > div > div > div > "
        "div.dx-fileuploader-input-wrapper > "
        "div.dx-widget.dx-button.dx-button-mode-contained.dx-button-normal."
        "dx-button-has-text.dx-fileuploader-button > div"
    )

    with page.expect_file_chooser(timeout=15000) as file_chooser_info:
        click_selector(page, file_button_selector)

    file_chooser_info.value.set_files(str(photo_path))
    page.wait_for_timeout(1000)

    save_button_selector = (
        "body > div.dx-overlay-wrapper.dx-datagrid-edit-popup.dx-popup-wrapper."
        "dx-overlay-shader > div > div.dx-toolbar.dx-widget."
        "dx-visibility-change-handler.dx-collection.dx-popup-bottom > div > "
        "div.dx-toolbar-after > div:nth-child(1) > div > div > div"
    )
    click_selector(page, save_button_selector)
    page.wait_for_timeout(1500)


def complete_boss_final_page(page, invoice_pdf: Path, invoice_data: dict):
    """
    Fill final page fields, upload invoice/signoff/photos, click Invoice Save,
    then stop before final submission so the user can review.
    """
    wo_no = invoice_data["wo_no"]
    inv_no = invoice_data["inv_no"]

    labor_description = (
        invoice_data.get("labor_description")
        or extract_labor_description_from_invoice(invoice_pdf)
    )
    if labor_description:
        fill_dx_input(page, "#InvoiceDetail_PerformComment", labor_description)

    signoff_pdf = invoice_data.get("signoff_pdf")
    if signoff_pdf:
        signoff_pdf = Path(signoff_pdf)
    else:
        signoff_pdf = find_boss_signoff_pdf(invoice_pdf, wo_no, inv_no)

    photos = invoice_data.get("photos")
    if photos:
        photos = [Path(photo) for photo in photos]
    else:
        photos = find_boss_photos(invoice_pdf.parent if invoice_pdf.parent.exists() else DROPBOX_2015)

    # Upload Invoice
    invoice_open_selector = (
        "#dx-a21a1ed2-b33b-ab64-cb7e-9b047553d7e4 > div > "
        "div.dx-toolbar-after > div:nth-child(3) > div > div > div"
    )
    invoice_comment_selector = "#dx_dx-e2b5b7e6-14ec-8da4-7597-dfd9920fb3d9_Comment"
    upload_boss_document(page, invoice_open_selector, invoice_comment_selector, "invoice", invoice_pdf)

    # Upload Signoff
    signoff_open_selector = (
        "#dx-a21a1ed2-b33b-ab64-cb7e-9b047553d7e4 > div > "
        "div.dx-toolbar-after > div:nth-child(2) > div > div > div"
    )
    signoff_comment_selector = "#dx_dx-eee9b5f4-1e2e-ba9b-e33e-bbd3530b5943_Comment"
    upload_boss_document(page, signoff_open_selector, signoff_comment_selector, "signoff", signoff_pdf)

    # Upload Photos
    for photo in photos:
        upload_boss_photo(page, photo)

    # Invoice Save button — stop after this for manual review before submit.
    invoice_save_selector = (
        "#dx-4fd75be9-12c4-23fd-db82-913dadc292da > div > "
        "div.dx-toolbar-before > div:nth-child(1) > div > div > div"
    )
    click_selector(page, invoice_save_selector)
    page.wait_for_timeout(3000)


def boss_upload(invoice_pdf: Path, invoice_data: dict):
    wo_no = invoice_data["wo_no"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(BOSS_URL)

        # Login
        page.fill("input[type='text']", BOSS_USERNAME)
        page.fill("input[type='password']", BOSS_PASSWORD)
        page.locator(".dx-button-content", has_text="Login").first.click()
        page.wait_for_load_state("networkidle")

        # Invoices page
        page.click("a[href='/Vendor/InvoiceListing']")
        page.wait_for_load_state("networkidle")

        # Add may open a new tab/window in Boss. Reassign page if it does.
        page = click_dx_button_allow_new_tab(page, "Add")

        # Select the WO/PO from the embedded grid, then click Step 1 Next.
        select_po_from_embedded_grid(page, wo_no)

        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)

        # Next screen
        page = click_dx_button_allow_new_tab(page, "Next")
        page.wait_for_load_state("domcontentloaded")
        wait_for_invoice_line_items(page)

        # Invoice number
        fill_dx_input(page, "input#Invnum", invoice_data["inv_no"])

        # Labor 1
        fill_dx_input(page, "input#LineItems_0__Quantity", invoice_data["labor_qty"])
        fill_dx_input(page, "input#LineItems_0__UnitPrice", invoice_data["labor_rate"])

        # Material
        fill_dx_input(page, "input#LineItems_3__Quantity", invoice_data["material_qty"])
        fill_dx_input(page, "input#LineItems_3__UnitPrice", invoice_data["material_total"])

        # Travel
        fill_dx_input(page, "input#LineItems_4__Quantity", invoice_data["travel_qty"])
        fill_dx_input(page, "input#LineItems_4__UnitPrice", invoice_data["travel_rate"])

        # Invoice date
        fill_dx_input(page, "input#Invdate", invoice_data["invoice_date"])

        # Final check before submit
        labor_value = page.locator("input#LineItems_0__UnitPrice").first.input_value()
        travel_value = page.locator("input#LineItems_4__UnitPrice").first.input_value()
        date_value = page.locator("input#Invdate").first.input_value()

        if str(invoice_data["labor_rate"]) not in labor_value:
            raise Exception(
                f"Labor rate did not retain. Expected {invoice_data['labor_rate']}, got {labor_value}"
            )

        if str(invoice_data["travel_rate"]) not in travel_value:
            raise Exception(
                f"Travel rate did not retain. Expected {invoice_data['travel_rate']}, got {travel_value}"
            )

        expected_date = normalize_date_mmddyy(invoice_data["invoice_date"])
        actual_date = normalize_date_mmddyy(date_value)

        if actual_date != expected_date:
            raise Exception(
                f"Invoice date did not retain. Expected {expected_date}, got {actual_date}"
            )

        click_dx_button(page, "Finish")

        # Final page: upload invoice, signoff, photos, then save for review.
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        complete_boss_final_page(page, invoice_pdf, invoice_data)

        # Stop here intentionally so the invoice can be reviewed before submit.
        page.wait_for_timeout(5000)
        browser.close()
