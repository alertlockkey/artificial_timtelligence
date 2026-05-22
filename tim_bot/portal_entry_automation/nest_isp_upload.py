import os
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, expect

load_dotenv()

NEST_USERNAME = os.getenv("NEST_USERNAME")
NEST_PASSWORD = os.getenv("NEST_PASSWORD")
DROPBOX_2015 = Path(os.getenv("DROPBOX_2015"))

LOGIN_URL = "https://providers.enternest.com/login.aspx"

def select_doc_type(page, row_index, value):
    selector = f"#docType{row_index}"

    page.wait_for_selector(selector)

    page.select_option(selector, value=value)

    page.dispatch_event(selector, "change")
    page.dispatch_event(selector, "blur")


def enter_wo_number(page, row_index, wo_no):
    field_selector = f"#plupload_wo{row_index}"
    field = page.locator(field_selector)

    field.click()
    field.press("Control+A")
    field.press("Backspace")
    page.wait_for_timeout(300)

    field.type(wo_no, delay=75)

    # Wait until at least one autocomplete item is actually visible
    page.wait_for_function("""
        () => Array.from(document.querySelectorAll('.ui-autocomplete li'))
            .some(li => li.offsetParent !== null && li.innerText.trim().length > 0)
    """)

    # Select from the currently open autocomplete menu
    field.press("ArrowDown")
    page.wait_for_timeout(200)
    field.press("Enter")
    page.wait_for_timeout(300)
    field.press("Tab")

    page.wait_for_timeout(700)

    actual_value = field.input_value()

    if wo_no not in actual_value:
        raise Exception(
            f"WO field row {row_index} did not retain value. "
            f"Expected {wo_no}, got {actual_value}"
        )

def upload_to_nest(invoice_pdf: Path, signoff_pdf: Path, wo_no: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(LOGIN_URL)

        page.fill("input[type='text']", NEST_USERNAME)
        page.fill("input[type='password']", NEST_PASSWORD)
        page.click("input[type='submit'], button[type='submit']")

        page.wait_for_load_state("networkidle")

        # Go to Mass Upload
        page.click("#massUpload_nav")
        page.wait_for_load_state("networkidle")

        # Add files
        with page.expect_file_chooser() as fc_info:
            page.click("#uploader_browse")

        file_chooser = fc_info.value
        file_chooser.set_files([
            str(invoice_pdf),
            str(signoff_pdf)
        ])

        # Let Nest render the rows
        page.wait_for_selector("#docType0")
        page.wait_for_selector("#docType1")
        page.wait_for_selector("#plupload_wo0")
        page.wait_for_selector("#plupload_wo1")

        # Row 0: Invoice PDF
        select_doc_type(page, 0, "ISP Invoice")
        enter_wo_number(page, 0, wo_no)

        page.wait_for_timeout(1000)

        # Row 1: Signoff / Work Order PDF
        select_doc_type(page, 1, "Work Order")
        enter_wo_number(page, 1, wo_no)

        doc0 = page.locator("#docType0").input_value()
        doc1 = page.locator("#docType1").input_value()
        wo0 = page.locator("#plupload_wo0").input_value()
        wo1 = page.locator("#plupload_wo1").input_value()

        print("Verification before upload:")
        print("Row 0:", doc0, wo0)
        print("Row 1:", doc1, wo1)

        if doc0 != "ISP Invoice" or wo0 != wo_no:
            raise Exception("Invoice row did not retain required values.")

        if doc1 != "Work Order" or wo1 != wo_no:
            raise Exception("Work Order row did not retain required values.")

        page.wait_for_timeout(1000)

        # Start upload
        page.click(".plupload_start")

        page.wait_for_timeout(8000)

        browser.close()


def archive_files(files):
    today_folder = DROPBOX_2015 / datetime.now().strftime("%m-%d-%Y")
    today_folder.mkdir(exist_ok=True)

    for file in files:
        destination = today_folder / file.name
        shutil.move(str(file), str(destination))

    return today_folder