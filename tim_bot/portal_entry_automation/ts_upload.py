import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from service_fusion_update import update_service_fusion_after_ts

load_dotenv()

TS_USERNAME = os.getenv("TS_USERNAME")
TS_PASSWORD = os.getenv("TS_PASSWORD")
DROPBOX_2015 = Path(os.getenv("DROPBOX_2015", r"C:\Users\Tim\Dropbox\2015"))

TS_URL = "https://affiliateconnect.truesource.com"
ORDERS_URL_PATH = "/dispatch/orders"


# -----------------------------------------------------------------------------
# Parsing / invoice helpers
# -----------------------------------------------------------------------------

TS_INVOICE_PATTERN = re.compile(
    r"^(?P<trip_no>\d+)-(?P<po_no>\d+)-\s*INVOICE\s*-\s*(?P<location>.+?)\s+WO#\s*(?P<wo_no>\d+)\s+INV#\s*(?P<inv_no>\d+)\.pdf$",
    re.I,
)


def parse_true_source_invoice_name(file: Path) -> dict:
    """Parse True Source invoice filename.

    Expected format:
        1-05236609- INVOICE - FAMILY DOLLAR WO# 03442788 INV# 56898.pdf
    """
    match = TS_INVOICE_PATTERN.match(file.name)
    if not match:
        raise ValueError(f"Invalid True Source invoice filename: {file.name}")

    data = match.groupdict()
    data["trip_no"] = data["trip_no"].strip()
    data["po_no"] = data["po_no"].strip()
    data["location"] = re.sub(r"\s+", " ", data["location"]).strip()
    data["wo_no"] = data["wo_no"].strip()
    data["inv_no"] = data["inv_no"].strip()
    return data


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


def normalize_money(value: str) -> str:
    value = str(value or "").replace("$", "").replace(",", "").strip()
    return f"{float(value):.2f}"


def normalize_date_mmddyyyy(value: str) -> str:
    raw = str(value or "").strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%m/%d/%Y")
        except ValueError:
            pass
    return raw


def calendar_aria_label(date_value: str) -> str:
    """Return the Angular Material calendar aria-label, e.g. May 20, 2026."""
    date_obj = datetime.strptime(normalize_date_mmddyyyy(date_value), "%m/%d/%Y")
    try:
        return date_obj.strftime("%-B %-d, %Y")  # Linux/macOS
    except ValueError:
        return date_obj.strftime("%B %#d, %Y")  # Windows


def extract_true_source_invoice_data(invoice_pdf: Path) -> dict:
    """Extract invoice amount and date from the invoice PDF."""
    text = extract_text_from_pdf(invoice_pdf)

    # Invoice date: prefer DATE label if present.
    date_match = re.search(r"\bDATE\b\s*\n?\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
    if not date_match:
        date_match = re.search(r"\bInvoice\s+Date\b\s*[:\n]?\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
    if not date_match:
        date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    if not date_match:
        raise ValueError(f"Could not find invoice date in {invoice_pdf}")

    invoice_date = normalize_date_mmddyyyy(date_match.group(1))

    # Invoice amount: prefer TOTAL DUE / TOTAL / PLEASE PAY.
    amount_patterns = [
        r"TOTAL\s+DUE\s*\$?\s*([\d,]+\.\d{2})",
        r"PLEASE\s+PAY\s*\$?\s*([\d,]+\.\d{2})",
        r"\bTOTAL\b\s*\$?\s*([\d,]+\.\d{2})",
        r"Invoice\s+Amount\s*[:\n]?\s*\$?\s*([\d,]+\.\d{2})",
    ]

    invoice_amount = None
    for pattern in amount_patterns:
        matches = re.findall(pattern, text, re.I)
        if matches:
            invoice_amount = normalize_money(matches[-1])
            break

    if not invoice_amount:
        # Last resort: use the largest dollar amount found.
        amounts = [float(x.replace(",", "")) for x in re.findall(r"\$\s*([\d,]+\.\d{2})", text)]
        if not amounts:
            raise ValueError(f"Could not find invoice amount in {invoice_pdf}")
        invoice_amount = f"{max(amounts):.2f}"

    return {
        "invoice_date": invoice_date,
        "invoice_amount": invoice_amount,
    }


# -----------------------------------------------------------------------------
# Playwright helpers
# -----------------------------------------------------------------------------


def fill_field(page, selector: str, value, timeout: int = 15000, delay: int = 40):
    field = page.locator(selector).first
    field.wait_for(state="visible", timeout=timeout)
    field.click()
    field.press("Control+A")
    field.press("Backspace")
    field.type(str(value), delay=delay)


def click_first_visible(page, selectors, timeout: int = 15000):
    last_error = None
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            return
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not click any selector: {selectors}. Last error: {last_error}")


def login_true_source(page):
    page.goto(TS_URL)
    page.wait_for_load_state("domcontentloaded")

    username = page.locator("#signInFormUsername:visible").first
    password = page.locator("#signInFormPassword:visible").first
    sign_in = page.locator("input.submitButton-customizable:visible").first

    username.wait_for(state="visible", timeout=20000)
    username.fill(TS_USERNAME)

    password.wait_for(state="visible", timeout=20000)
    password.fill(TS_PASSWORD)

    sign_in.wait_for(state="visible", timeout=20000)
    sign_in.click()

    page.wait_for_load_state("networkidle")

    # Handle post-login announcement popup (if it appears)
    try:
        popup_button = page.locator(
            "#mat-mdc-dialog-0 button:has-text('Got it'), "
            "#mat-mdc-dialog-0 button:has-text('Close'), "
            "#mat-mdc-dialog-0 button span.mdc-button__label"
        ).first

        popup_button.wait_for(state="visible", timeout=5000)
        popup_button.click()

        page.wait_for_timeout(1000)

    except PlaywrightTimeoutError:
        pass  # No popup appeared, continue normally


def go_to_orders(page):
    # Prefer the stable route when possible, with the provided selector as fallback.
    try:
        page.goto(TS_URL.rstrip("/") + ORDERS_URL_PATH)
        page.wait_for_load_state("networkidle")
    except Exception:
        pass

    if page.locator("shared-filters input[placeholder='Search orders']").count() == 0:
        click_first_visible(page, [
            "a[href='/dispatch/orders']",
            "body > app-root > dispatch-root > core-header > mat-toolbar > nav > ul > li:nth-child(3) > a",
            "a:has-text('Orders')",
        ])
        page.wait_for_load_state("networkidle")


def open_invoice_dialog_for_wo(page, wo_no: str):
    search_selector = "body > app-root > dispatch-root > div > app-orders > section > shared-filters > div > input"
    fallback_selector = "shared-filters input[placeholder='Search orders'], input[placeholder='Search orders']"

    try:
        fill_field(page, search_selector, wo_no, timeout=10000, delay=60)
    except Exception:
        fill_field(page, fallback_selector, wo_no, timeout=10000, delay=60)

    page.wait_for_timeout(3000)

    # Wait for the filtered order row containing this WO.
    row = page.locator("o-orders-table table tbody tr", has_text=str(wo_no)).first
    try:
        row.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        # Some tables do not render the WO text in the visible row after filtering.
        row = page.locator("o-orders-table table tbody tr").first
        row.wait_for(state="visible", timeout=15000)

    row.hover()

    invoice_button = row.locator("td.cdk-column-invoice button, td.mat-column-invoice button").first
    try:
        invoice_button.wait_for(state="visible", timeout=10000)
        invoice_button.click()
    except Exception:
        page.locator(
            "body > app-root > dispatch-root > div > app-orders > div > o-orders-table > table > tbody > tr > td.mat-mdc-cell.mdc-data-table__cell.cdk-cell.doc.cdk-column-invoice.mat-column-invoice.ng-star-inserted > button"
        ).first.click(force=True)

    page.wait_for_selector("shared-file-upload-dialog", timeout=20000)


def fill_invoice_dialog(page, invoice_data: dict):
    inv_no = invoice_data["inv_no"]
    po_no = invoice_data["po_no"]
    amount = invoice_data["invoice_amount"]
    invoice_date = invoice_data["invoice_date"]

    # Invoice number
    fill_field(
        page,
        "shared-file-upload-dialog input[aria-label='Invoice Number'], #mat-mdc-dialog-0 shared-file-upload-dialog div:nth-child(2) div:nth-child(1) input",
        inv_no,
    )

    # Invoice amount
    fill_field(
        page,
        "shared-file-upload-dialog input[aria-label='Invoice Amount'], shared-file-upload-dialog input[type='number']",
        amount,
    )

    # PO/order assertion and selection if needed.
    order_select = page.locator("shared-file-upload-dialog select.full-width, shared-file-upload-dialog select").first
    order_select.wait_for(state="visible", timeout=15000)

    options_text = order_select.locator("option").all_inner_texts()
    normalized_options = [re.sub(r"\s+", "", text) for text in options_text]
    if po_no not in normalized_options:
        raise Exception(f"True Source PO mismatch. Expected {po_no}; options were {options_text}")

    try:
        order_select.select_option(value=po_no)
    except Exception:
        order_select.select_option(label=re.compile(rf"\s*{re.escape(po_no)}\s*"))

    # Date picker: click calendar button with dynamic aria-label.
    aria = calendar_aria_label(invoice_date)
    date_button = page.locator(f"shared-calendar button[aria-label='{aria}']").first
    date_button.wait_for(state="visible", timeout=15000)
    date_button.click()


def attach_invoice_pdf(page, invoice_pdf: Path):
    if not invoice_pdf.exists():
        raise FileNotFoundError(f"Invoice PDF does not exist: {invoice_pdf}")

    dropzone_selector = "shared-file-upload-dialog ngx-dropzone"
    dropzone = page.locator(dropzone_selector).first
    dropzone.wait_for(state="visible", timeout=15000)

    try:
        with page.expect_file_chooser(timeout=5000) as chooser_info:
            dropzone.click()
        chooser_info.value.set_files(str(invoice_pdf))
    except PlaywrightTimeoutError:
        # Fallback for Angular dropzone implementations with hidden file input.
        file_input = page.locator("shared-file-upload-dialog input[type='file']").first
        file_input.set_input_files(str(invoice_pdf))

    page.wait_for_timeout(1500)


def submit_invoice_dialog(page):
    click_first_visible(page, [
        "shared-file-upload-dialog button.mat-primary:has-text('Submit')",
        "#mat-mdc-dialog-0 > div > div > shared-file-upload-dialog > div > div.row.no-margins.right-align.full-width.ng-star-inserted > button.mdc-button.mat-mdc-button-base.mat-mdc-button.mat-primary.ng-star-inserted",
        "shared-file-upload-dialog button:has-text('Submit')",
    ], timeout=15000)
    page.wait_for_timeout(3000)

def archive_submitted_invoice(invoice_pdf: Path):
    archive_folder = DROPBOX_2015 / datetime.now().strftime("%m-%d-%y")
    archive_folder.mkdir(exist_ok=True)

    destination = archive_folder / invoice_pdf.name
    shutil.move(str(invoice_pdf), str(destination))

    print(f"Moved submitted invoice to: {destination}")
    return destination



# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------


def ts_upload(invoice_pdf: Path, submit: bool = True):
    filename_data = parse_true_source_invoice_name(invoice_pdf)
    pdf_data = extract_true_source_invoice_data(invoice_pdf)

    invoice_data = {
        **filename_data,
        **pdf_data,
    }

    archived_file = None
    should_update_service_fusion = False

    # Important: keep all True Source browser work inside this Playwright context.
    # Do NOT call Service Fusion from inside this block, because Service Fusion
    # starts its own sync_playwright() context.
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            login_true_source(page)
            go_to_orders(page)
            open_invoice_dialog_for_wo(page, invoice_data["wo_no"])
            fill_invoice_dialog(page, invoice_data)
            attach_invoice_pdf(page, invoice_pdf)

            if submit:
                submit_invoice_dialog(page)
                print(
                    f"Submitted True Source invoice {invoice_data['inv_no']} "
                    f"for WO {invoice_data['wo_no']} / PO {invoice_data['po_no']}."
                )

                archived_file = archive_submitted_invoice(invoice_pdf)
                should_update_service_fusion = True
            else:
                print("True Source invoice dialog filled and file attached. Stopping before submit for review.")
                page.wait_for_timeout(10000)

        finally:
            browser.close()

    # Service Fusion runs AFTER the True Source Playwright context has fully closed.
    # This prevents: "using Playwright Sync API inside the asyncio loop".
    if submit and should_update_service_fusion and archived_file:
        update_service_fusion_after_ts(invoice_data, archived_file)


if __name__ == "__main__":
    # Manual test: first matching True Source invoice in DROPBOX_2015.
    matches = sorted(DROPBOX_2015.glob("*- INVOICE - * WO# * INV# *.pdf"))
    if not matches:
        raise FileNotFoundError(f"No True Source invoice PDFs found in {DROPBOX_2015}")

    ts_upload(matches[0], submit=True)
