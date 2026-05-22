import os
import re
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


def click_dx_button(page, label: str, timeout: int = 2000):
    """Click a DevExtreme button by its visible label."""
    button = page.get_by_role("button", name=label).first
    button.wait_for(state="visible", timeout=timeout)
    button.click()


def click_dx_button_allow_new_tab(page, label: str, timeout: int = 2000):
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
        # No new tab opened; keep using the current page.
        return page


def fill_dx_input(page, selector: str, value):
    """Fill DevExtreme text/number inputs and blur so the widget keeps the value."""
    field = page.locator(selector).first
    field.wait_for(state="visible", timeout=2000)
    field.click()
    field.press("Control+A")
    field.press("Backspace")
    field.type(str(value), delay=50)
    field.press("Tab")


def wait_for_invoice_line_items(page):
    """Wait until the invoice line item form is ready."""
    page.wait_for_selector("input#LineItems_0__Quantity", timeout=3000)
    page.wait_for_selector("input#LineItems_0__UnitPrice", timeout=3000)
    page.wait_for_selector("input#LineItems_3__UnitPrice", timeout=3000)
    page.wait_for_selector("input#LineItems_4__UnitPrice", timeout=3000)
    page.wait_for_selector("input#Invdate", timeout=3000)


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

        # Wait for the PO / WO field on whichever page is now active.
        page.wait_for_selector("input#Ponum", timeout=2000)

        # WO / PO number
        fill_dx_input(page, "input#Ponum", wo_no)

        # Next screens. These usually remain in the same tab, but the helper is
        # safe if Boss opens another page later.
        page = click_dx_button_allow_new_tab(page, "Next")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)

        page = click_dx_button_allow_new_tab(page, "Next")
        page.wait_for_load_state("domcontentloaded")
        wait_for_invoice_line_items(page)

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

        if date_value != str(invoice_data["invoice_date"]):
            raise Exception(
                f"Invoice date did not retain. Expected {invoice_data['invoice_date']}, got {date_value}"
            )

        # Finish may also be duplicated in DevExtreme, so use the same helper.
        click_dx_button(page, "Finish")

        page.wait_for_timeout(5000)
        browser.close()
