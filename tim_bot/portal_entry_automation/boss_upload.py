# This script creates a new invoice in the portal.
# Resume testing with a new BOSS invoice.

import os
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


# -----------------------------------------------------------------------------
# Parsing / data helpers
# -----------------------------------------------------------------------------

def parse_boss_invoice_name(file: Path):
    pattern = re.compile(
        r"INV Boss Facility WO# (?P<wo_no>.+?) INV# (?P<inv_no>.+?)\.pdf$",
        re.I,
    )
    match = pattern.match(file.name)
    if not match:
        raise ValueError(f"Invalid Boss invoice filename: {file.name}")

    return match.group("wo_no").strip(), match.group("inv_no").strip()


def corresponding_boss_signoff(invoice_pdf: Path, wo_no: str, inv_no: str) -> Path:
    signoff_pdf = invoice_pdf.parent / f"WO Boss Facility WO# {wo_no} INV# {inv_no}.pdf"
    if not signoff_pdf.exists():
        raise FileNotFoundError(f"Missing Boss signoff PDF: {signoff_pdf}")
    return signoff_pdf


def boss_photos(folder: Path):
    photos = sorted(folder.glob("boss*.jpg")) + sorted(folder.glob("boss*.jpeg")) + sorted(folder.glob("boss*.png"))
    return photos


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF using PyMuPDF when available, with pypdf fallback."""
    try:
        import fitz  # PyMuPDF

        parts = []
        with fitz.open(str(pdf_path)) as doc:
            for page in doc:
                parts.append(page.get_text("text"))
        return "\n".join(parts)
    except Exception:
        pass

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise RuntimeError(f"Could not extract text from {pdf_path}: {exc}")


def clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_labor_description(invoice_pdf: Path) -> str:
    """
    Pull the Labor description from the invoice.

    Expected source text example:
      Labor 1 Man per hour Standard to adjust ... proper operation.
      2 95.00 190.00
    """
    text = extract_text_from_pdf(invoice_pdf)

    match = re.search(
        r"(Labor\s+1\s+Man\s+per\s+hour\s+Standard\s+.*?)(?:\n\s*\d+(?:\.\d+)?\s+\d+[\d,.]*\s+\d+[\d,.]*|\n\s*SUBTOTAL)",
        text,
        re.I | re.S,
    )
    if match:
        return clean_spaces(match.group(1))

    # Fallback: take from Labor through the next subtotal-ish marker.
    match = re.search(r"(Labor\s+.*?)(?:SUBTOTAL|TAX|TOTAL)", text, re.I | re.S)
    if match:
        return clean_spaces(match.group(1))

    raise ValueError(f"Could not find labor description in {invoice_pdf}")


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


# -----------------------------------------------------------------------------
# Playwright helpers
# -----------------------------------------------------------------------------

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


def fill_multiline_or_input(page, selector: str, value):
    field = page.locator(selector).first
    field.wait_for(state="visible", timeout=10000)
    field.click()
    field.press("Control+A")
    field.press("Backspace")
    field.type(str(value), delay=10)
    field.press("Tab")


def click_selector(page, selector: str, timeout: int = 10000):
    item = page.locator(selector).first
    item.wait_for(state="visible", timeout=timeout)
    item.click()


def set_file_from_button(page, button_selector: str, file_path: Path, timeout: int = 10000):
    if not file_path.exists():
        raise FileNotFoundError(f"Upload file not found: {file_path}")

    with page.expect_file_chooser(timeout=timeout) as chooser_info:
        click_selector(page, button_selector, timeout=timeout)

    chooser = chooser_info.value
    chooser.set_files(str(file_path))
    page.wait_for_timeout(1000)


# -----------------------------------------------------------------------------
# Existing invoice workflow
# -----------------------------------------------------------------------------

def open_existing_invoice_from_listing(page, wo_no: str):
    """On Vendor Invoice Listing, filter by WO number and open the edit invoice row."""
    page.wait_for_selector("input#Ponum", timeout=15000)
    # Enter WO#
    fill_dx_input(page, "input#Ponum", wo_no)

    page.wait_for_timeout(1500)

    # Hover/focus the filtered row first
    row = page.locator("#InvoiceListingGrid tr.dx-data-row", has_text=str(wo_no)).first
    row.wait_for(state="visible", timeout=10000)
    row.hover()
    row.click()

    page.wait_for_timeout(500)

    # Now click the edit icon, allowing hidden/hover-triggered DevExtreme icon
    edit_button = row.locator("a.dx-link.dx-icon-edit").first
    edit_button.click(force=True)

    page.wait_for_timeout(2000)

    # Wait for the invoice detail page/popup to actually load
    page.wait_for_selector(
        "textarea#InvoiceDetail_PerformComment, input#InvoiceDetail_PerformComment, #InvoiceDetail_PerformComment",
        timeout=20000
    )

def fill_invoice_perform_comment(page, labor_description: str):
    fill_multiline_or_input(page, "#InvoiceDetail_PerformComment", labor_description)


# -----------------------------------------------------------------------------
# Document upload helpers for the edit/final page
# -----------------------------------------------------------------------------

INVOICE_UPLOAD_BUTTON = (
    "#dx-a21a1ed2-b33b-ab64-cb7e-9b047553d7e4 > div > "
    "div.dx-toolbar-after > div:nth-child(3) > div > div > div"
)

SIGNOFF_UPLOAD_BUTTON = (
    "#dx-a21a1ed2-b33b-ab64-cb7e-9b047553d7e4 > div > "
    "div.dx-toolbar-after > div:nth-child(2) > div > div > div"
)

PHOTO_UPLOAD_BUTTON = (
    "#dx-a21a1ed2-b33b-ab64-cb7e-9b047553d7e4 > div > "
    "div.dx-toolbar-after > div:nth-child(1) > div > div > div"
)

POPUP_SAVE_BUTTON = (
    "body > div.dx-overlay-wrapper.dx-datagrid-edit-popup.dx-popup-wrapper."
    "dx-overlay-shader > div > div.dx-toolbar.dx-widget.dx-visibility-change-handler."
    "dx-collection.dx-popup-bottom > div > div.dx-toolbar-after > "
    "div:nth-child(1) > div > div > div"
)

FILE_UPLOADER_BUTTON = (
    "#DocumentFileUploader > div > div > div > div.dx-fileuploader-input-wrapper > "
    "div.dx-widget.dx-button.dx-button-mode-contained.dx-button-normal."
    "dx-button-has-text.dx-fileuploader-button > div"
)

INVOICE_SAVE_BUTTON = (
    "#dx-4fd75be9-12c4-23fd-db82-913dadc292da > div > "
    "div.dx-toolbar-before > div:nth-child(1) > div > div > div"
)


def current_popup_comment_field(page):
    # DevExtreme-generated IDs change, so prefer the visible popup's *_Comment field.
    return page.locator("input[id$='_Comment'], textarea[id$='_Comment']").last


def save_current_popup(page):
    try:
        click_selector(page, POPUP_SAVE_BUTTON, timeout=10000)
    except PlaywrightTimeoutError:
        page.get_by_role("button", name="Save").last.click()
    page.wait_for_timeout(1500)


def upload_standard_document(page, add_button_selector: str, comment: str, file_path: Path):
    click_selector(page, add_button_selector, timeout=15000)
    page.wait_for_selector("#DocumentFileUploader", timeout=15000)

    comment_field = current_popup_comment_field(page)
    comment_field.wait_for(state="visible", timeout=10000)
    comment_field.click()
    comment_field.press("Control+A")
    comment_field.press("Backspace")
    comment_field.type(comment, delay=25)

    set_file_from_button(page, FILE_UPLOADER_BUTTON, file_path)
    save_current_popup(page)


def upload_photo_document(page, photo_path: Path):
    click_selector(page, PHOTO_UPLOAD_BUTTON, timeout=15000)
    page.wait_for_selector("#DocumentFileUploader", timeout=15000)

    # Select Type = Photos. DevExtreme IDs vary, so use the visible type input/dropdown first.
    type_field = page.locator("input[id$='_Type']").last
    type_field.wait_for(state="visible", timeout=10000)
    type_field.click()
    page.wait_for_timeout(500)

    try:
        page.locator(".dx-list-item", has_text="Photos").first.click(timeout=5000)
    except Exception:
        # Fallback: first option in the visible dropdown.
        page.locator(".dx-list-item").first.click(timeout=5000)

    comment_field = current_popup_comment_field(page)
    comment_field.wait_for(state="visible", timeout=10000)
    comment_field.click()
    comment_field.press("Control+A")
    comment_field.press("Backspace")
    comment_field.type("photo", delay=25)

    set_file_from_button(page, FILE_UPLOADER_BUTTON, photo_path)
    save_current_popup(page)


def upload_final_page_documents(page, invoice_pdf: Path, invoice_data: dict):
    wo_no = invoice_data["wo_no"]
    inv_no = invoice_data["inv_no"]
    signoff_pdf = corresponding_boss_signoff(invoice_pdf, wo_no, inv_no)
    photos = boss_photos(invoice_pdf.parent)

    labor_description = invoice_data.get("labor_description") or extract_labor_description(invoice_pdf)
    fill_invoice_perform_comment(page, labor_description)

    upload_standard_document(page, INVOICE_UPLOAD_BUTTON, "invoice", invoice_pdf)
    upload_standard_document(page, SIGNOFF_UPLOAD_BUTTON, "signoff", signoff_pdf)

    for photo in photos:
        upload_photo_document(page, photo)

    # Save invoice, then stop for manual review/submission.
    click_selector(page, INVOICE_SAVE_BUTTON, timeout=15000)
    page.wait_for_timeout(3000)


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------

def boss_upload(invoice_pdf: Path, invoice_data: dict):
    """
    Boss existing-invoice workflow:
      1. Log into Boss
      2. Go to Invoices
      3. Search by WO# and open the existing invoice for edit
      4. Add labor description and upload invoice/signoff/photos
      5. Click invoice Save and stop for manual review/submission
    """
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

        # Open the existing invoice, do not create a new one.
        open_existing_invoice_from_listing(page, wo_no)

        # Last-page preparation/upload steps, then save and stop.
        upload_final_page_documents(page, invoice_pdf, invoice_data)

        print("Boss invoice saved with documents attached. Stopping before submit for review.")
        page.wait_for_timeout(10000)
        browser.close()
