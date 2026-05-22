from __future__ import annotations

import argparse
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from dotenv import load_dotenv
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


@dataclass
class Settings:
    watch_folder: Path
    processed_folder: Path
    error_folder: Path
    sf_company_id: str
    sf_username: str
    sf_password: str
    headless: bool
    assigned_tech: str
    current_status: str
    note_text: str
    renamed_pdf: str


def load_settings() -> Settings:
    load_dotenv()
    watch = Path(os.getenv("WATCH_FOLDER", "quote_approval")).expanduser()
    processed = Path(os.getenv("PROCESSED_FOLDER", watch / "processed")).expanduser()
    errors = Path(os.getenv("ERROR_FOLDER", watch / "errors")).expanduser()
    return Settings(
        watch_folder=watch,
        processed_folder=processed,
        error_folder=errors,
        sf_company_id=os.getenv("SERVICE_FUSION_COMPANY_ID", ""),
        sf_username=os.getenv("SERVICE_FUSION_USERNAME", ""),
        sf_password=os.getenv("SERVICE_FUSION_PASSWORD", ""),
        headless=os.getenv("HEADLESS", "0").strip() == "1",
        assigned_tech=os.getenv("ASSIGNED_TECH", "Sean Flanagan"),
        current_status=os.getenv("CURRENT_STATUS", "Dispatched"),
        note_text=os.getenv("NOTE_TEXT", "QUOTE APPROVAL IN DOCS"),
        renamed_pdf=os.getenv("RENAMED_PDF", "Quote Approval Email.pdf"),
    )


def wait_until_file_is_stable(path: Path, checks: int = 3, delay: float = 1.0) -> None:
    last_size = -1
    stable_count = 0
    while stable_count < checks:
        size = path.stat().st_size
        if size == last_size and size > 0:
            stable_count += 1
        else:
            stable_count = 0
            last_size = size
        time.sleep(delay)


def extract_pdf_text(pdf_path: Path) -> str:
    with fitz.open(pdf_path) as doc:
        return "\n".join(page.get_text("text") for page in doc)


def extract_wo_or_po(text: str) -> str:
    """Extracts the best WO/PO candidate from quote approval PDFs.

    The priority is intentionally strict to avoid false positives from words like
    workorders, work, portal, etc.
    """
    patterns = [
        r"ISP\s*WO\s*#\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{4,})",
        r"ISP\s*Work\s*Order\s*#\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{4,})",
        r"Work\s*Order\s*#\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{4,})",
        r"\bWO\s*#\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{4,})",
        r"\bPO\s*#\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{4,})",
        r"\bPO\s*Number\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{4,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().upper()
    raise ValueError("Could not find a WO/PO number in the PDF.")


def rename_for_upload(pdf_path: Path, settings: Settings) -> Path:
    target = pdf_path.with_name(settings.renamed_pdf)
    if pdf_path.resolve() == target.resolve():
        return target
    if target.exists():
        target.unlink()
    pdf_path.rename(target)
    return target


def fill_kendo_dropdown(page: Page, label_text: str, value: str) -> None:
    """Best-effort Kendo/Select2 style dropdown updater by nearby label text."""
    label = page.get_by_text(label_text, exact=False).first
    label.wait_for(timeout=10_000)
    container = label.locator("xpath=ancestor::*[self::div or self::td or self::tr][1]")
    # Try combobox/input inside the same row/container.
    candidates = [
        container.locator("input[role='combobox']").first,
        container.locator("span[role='combobox']").first,
        container.locator("input").first,
        page.locator(f"xpath=//*[contains(normalize-space(.), '{label_text}')]/following::input[1]").first,
    ]
    for candidate in candidates:
        try:
            candidate.click(timeout=3_000)
            try:
                candidate.fill(value, timeout=3_000)
            except Exception:
                page.keyboard.type(value)
            page.keyboard.press("Enter")
            return
        except Exception:
            continue
    raise RuntimeError(f"Could not update dropdown/field near label: {label_text}")


def first_visible(page_or_locator, selectors: list[str], timeout: int = 5_000):
    """Return the first visible locator from a list of selector fallbacks."""
    deadline = time.time() + (timeout / 1000)
    last_error: Optional[Exception] = None
    while time.time() < deadline:
        for selector in selectors:
            try:
                locator = page_or_locator.locator(selector).first
                if locator.count() and locator.is_visible(timeout=500):
                    return locator
            except Exception as exc:
                last_error = exc
        time.sleep(0.25)
    if last_error:
        raise last_error
    raise PlaywrightTimeoutError("No visible locator matched the provided selectors.")


def fill_first_visible(page: Page, selectors: list[str], value: str, field_name: str) -> None:
    field = first_visible(page, selectors, timeout=8_000)
    field.fill(value)
    print(f"Filled Service Fusion {field_name}.")


def login_if_needed(page: Page, settings: Settings) -> None:
    """Service Fusion login flow using the same env vars as service_fusion_po_automation.

    Required .env variables:
      SERVICE_FUSION_COMPANY_ID=company
      SERVICE_FUSION_USERNAME=username
      SERVICE_FUSION_PASSWORD=password

    The selectors are intentionally broad because Service Fusion login fields may vary
    slightly by account/session, but these target the normal Company ID / Username /
    Password form instead of the older email-only fallback.
    """
    # If the jobs page loads without showing a login form, keep going.
    login_field_visible = page.locator("input[type='password'], input[name*='password' i]").first
    try:
        login_field_visible.wait_for(timeout=6_000)
    except PlaywrightTimeoutError:
        return

    missing = []
    if not settings.sf_company_id:
        missing.append("SERVICE_FUSION_COMPANY_ID")
    if not settings.sf_username:
        missing.append("SERVICE_FUSION_USERNAME")
    if not settings.sf_password:
        missing.append("SERVICE_FUSION_PASSWORD")
    if missing:
        raise RuntimeError(f"Missing required Service Fusion login variables in .env: {', '.join(missing)}")

    fill_first_visible(
        page,
        [
            "input[name='company']",
            "input[name='company_id']",
            "input[name*='company' i]",
            "input[id*='company' i]",
            "input[placeholder*='Company' i]",
            "input[aria-label*='Company' i]",
        ],
        settings.sf_company_id,
        "company ID",
    )
    fill_first_visible(
        page,
        [
            "input[name='username']",
            "input[name*='username' i]",
            "input[id*='username' i]",
            "input[placeholder*='Username' i]",
            "input[aria-label*='Username' i]",
            "input[type='email']",
        ],
        settings.sf_username,
        "username",
    )
    fill_first_visible(
        page,
        [
            "input[type='password']",
            "input[name*='password' i]",
            "input[id*='password' i]",
            "input[placeholder*='Password' i]",
        ],
        settings.sf_password,
        "password",
    )

    first_visible(
        page,
        [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Login')",
            "button:has-text('Log In')",
            "button:has-text('Sign In')",
        ],
        timeout=8_000,
    ).click()
    page.wait_for_load_state("networkidle", timeout=30_000)



def search_global_search(page: Page, wo_po: str) -> None:
    """Search Service Fusion's top Global Search box for a WO/PO number.

    The Global Search input is a Kendo AutoComplete with a dynamic id, so do not
    target the id. This prefers stable attributes from the wrapper/input that
    Service Fusion renders:
      div.search-container input[kendosearchbar][placeholder="Global Search"]
    """
    search_selectors = [
        "div.search-container input[kendosearchbar][placeholder='Global Search']",
        "kendo-autocomplete input[kendosearchbar][placeholder='Global Search']",
        "input[kendosearchbar][placeholder='Global Search']",
        "input[role='combobox'][placeholder='Global Search']",
        "input[aria-autocomplete='list'][placeholder='Global Search']",
        "input[placeholder='Global Search']",
    ]

    search = first_visible(page, search_selectors, timeout=15_000)
    search.click()

    # Kendo inputs sometimes retain a previous value, so clear as a user would.
    try:
        search.press("Control+A")
        search.press("Backspace")
    except Exception:
        pass

    try:
        search.fill(wo_po)
    except Exception:
        page.keyboard.type(wo_po)

    # Let the autocomplete list populate, then choose the closest result. In some
    # Service Fusion sessions Enter opens the top result; in others clicking the
    # text is more reliable.
    page.wait_for_timeout(750)
    result_selectors = [
        f"[role='option']:has-text('{wo_po}')",
        f"li:has-text('{wo_po}')",
        f".k-list-item:has-text('{wo_po}')",
        f".k-list .k-item:has-text('{wo_po}')",
        f"text={wo_po}",
    ]
    for selector in result_selectors:
        try:
            result = page.locator(selector).first
            if result.count() and result.is_visible(timeout=1_500):
                result.click()
                page.wait_for_load_state("networkidle", timeout=20_000)
                return
        except Exception:
            continue

    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle", timeout=20_000)


def select_select2_result(page: Page, value: str, field_name: str) -> None:
    """Select a visible Select2 dropdown result by text."""
    result_selectors = [
        ".select2-drop-active .select2-results li",
        ".select2-results li",
        ".select2-result-label",
    ]
    for selector in result_selectors:
        try:
            result = page.locator(selector, has_text=value).first
            if result.count() and result.is_visible(timeout=5_000):
                result.click()
                print(f"Selected {value!r} for Service Fusion {field_name}.")
                return
        except Exception:
            continue
    raise RuntimeError(f"Could not select {value!r} from the Select2 results for {field_name}.")


def set_job_status(page: Page, status: str) -> None:
    """Update Service Fusion Current Status using the inline editable select.

    Service Fusion renders the current job status as an x-editable control:
      <a id="statusManual" ...><span id="job-view-master-status">...</span></a>

    Clicking it opens a real <select class="input-medium"> inside
    .editable-container. For Dispatched, selecting by the known option value is
    the most reliable way to avoid accidentally picking nearby values like
    "To Do Lists".
    """
    status_values = {
        "dispatched": "1018710314",
    }
    desired_value = status_values.get(status.strip().lower())

    opener = first_visible(
        page,
        [
            "#statusManual",
            "#job-view-master-status",
            "a.editable:has(#job-view-master-status)",
            "a[data-title='Select Status']",
        ],
        timeout=10_000,
    )
    opener.click()

    select_locator = page.locator(".editable-container select.input-medium, .editable-container select").first
    select_locator.wait_for(state="visible", timeout=10_000)

    if desired_value:
        select_locator.select_option(value=desired_value)
    else:
        select_locator.select_option(label=status)

    # Give the inline editable control a moment to commit the change and verify when possible.
    try:
        page.wait_for_selector(f"#job-view-master-status:has-text('{status}')", timeout=8_000)
    except Exception:
        page.wait_for_timeout(1_000)

    print(f"Set Service Fusion Current Status to {status!r}.")


def set_select2_assigned_tech(page: Page, tech_name: str) -> None:
    """Update the Assigned Techs Select2 field.

    The user-provided input is the Select2 search field:
      <input class="select2-input select2-default" id="s2id_autogen1" ...>

    Since Select2 autogen ids can shift, this tries that exact input first,
    then falls back to an Assigned Techs-nearby Select2 container/input.
    """
    # First try the exact element the user found.
    input_selectors = [
        "#s2id_autogen1",
        "input.select2-input.select2-default[id^='s2id_autogen']",
        "xpath=//*[contains(normalize-space(.), 'Assigned Techs')]/following::input[contains(@class, 'select2-input')][1]",
    ]
    try:
        tech_input = first_visible(page, input_selectors, timeout=5_000)
        tech_input.click()
    except Exception:
        # Some Select2 fields hide the input until the container is clicked.
        container_selectors = [
            "xpath=//*[contains(normalize-space(.), 'Assigned Techs')]/following::*[contains(@class, 'select2-container')][1]",
            ".select2-container:has(.select2-choices)",
            ".select2-container",
        ]
        container = first_visible(page, container_selectors, timeout=10_000)
        container.click()
        tech_input = first_visible(
            page,
            [
                ".select2-drop-active input.select2-input",
                "input.select2-input:visible",
                "input.select2-input[id^='s2id_autogen']",
            ],
            timeout=10_000,
        )

    try:
        tech_input.fill(tech_name)
    except Exception:
        page.keyboard.type(tech_name)

    page.wait_for_timeout(500)
    select_select2_result(page, tech_name, "Assigned Techs")


def upload_file(page: Page, pdf_path: Path) -> None:
    # Preferred Playwright pattern: arm file chooser before clicking Add files.
    try:
        with page.expect_file_chooser(timeout=10_000) as chooser_info:
            page.locator("#plupload-demo-box_browse, a.plupload_add").first.click()
        chooser_info.value.set_files(str(pdf_path))
        return
    except Exception:
        pass

    # Fallback: set any file input directly.
    file_inputs = page.locator("input[type='file']")
    if file_inputs.count() == 0:
        raise RuntimeError("Could not find a file input for document upload.")
    file_inputs.first.set_input_files(str(pdf_path))


def start_document_upload(page: Page) -> None:
    """Click Service Fusion/Plupload Start upload after the file has been queued.

    Selecting a file only adds it to the upload queue. This button actually
    starts the upload before the job is saved.
    """
    start_button = page.locator(
        "a.plupload_start, a.btn.plupload_start, a:has-text('Start upload')"
    ).first
    start_button.wait_for(state="visible", timeout=10_000)
    start_button.click()

    # Basic completion wait. We can replace this later with a Service Fusion-
    # specific success selector once we capture the upload-complete DOM.
    page.wait_for_timeout(3_000)




def close_upload_modal(page: Page) -> None:
    """Close the document upload modal before clicking Save Job."""
    close_button = page.locator("#upload-close, button#upload-close, button.close[data-dismiss='modal']").first
    try:
        close_button.wait_for(state="visible", timeout=8_000)
        close_button.click()
        page.wait_for_timeout(500)
        print("Closed Service Fusion upload modal.")
    except Exception:
        # If the modal has already closed on its own, continue to Save Job.
        print("Upload modal close button was not visible; continuing to Save Job.")


def automate_service_fusion(wo_po: str, pdf_path: Path, settings: Settings) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=settings.headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(20_000)

        page.goto("https://admin.servicefusion.com/jobs/", wait_until="domcontentloaded")
        login_if_needed(page, settings)
        page.goto("https://admin.servicefusion.com/jobs/", wait_until="networkidle")

        search_global_search(page, wo_po)

        # Click the best matching search result/job row if needed.
        try:
            page.get_by_text(wo_po, exact=False).first.click(timeout=8_000)
            page.wait_for_load_state("networkidle")
        except Exception:
            pass

        # Edit button/icon.
        page.locator("i.icol-page-white-edit").first.click()
        page.wait_for_load_state("networkidle")

        # Summary tab updates. Status is an inline editable select; Assigned Techs is Select2.
        set_job_status(page, settings.current_status)
        set_select2_assigned_tech(page, settings.assigned_tech)

        # Add note. The Add Notes button reveals/focuses the stable textarea:
        #   <textarea id="add-new-note" ... name="add-new-note"></textarea>
        page.locator("button:has-text('Add Notes')").first.click()
        note_box = page.locator("#add-new-note").first
        note_box.wait_for(state="visible", timeout=10_000)
        note_box.click()
        note_box.fill(settings.note_text)
        page.locator("#add-new-note-btn, button.addNoteBtn").first.click()

        # Docs tab and upload.
        page.locator("#documents-title, a[href='#documents']").first.click()
        page.locator("#add-new-doc-btn, button:has-text('Upload New')").first.click()
        upload_file(page, pdf_path)

        # Start the queued Plupload upload before saving the job.
        start_document_upload(page)

        # Close upload modal before saving so it does not block the Save Job button.
        close_upload_modal(page)

        # Save job.
        page.locator("#createjobbottom, button:has-text('Save Job')").first.click()
        page.wait_for_load_state("networkidle")
        browser.close()


def process_pdf(pdf_path: Path, settings: Settings) -> None:
    wait_until_file_is_stable(pdf_path)
    text = extract_pdf_text(pdf_path)
    wo_po = extract_wo_or_po(text)
    upload_pdf = rename_for_upload(pdf_path, settings)
    print(f"Found WO/PO: {wo_po}")
    print(f"Renamed PDF: {upload_pdf}")
    automate_service_fusion(wo_po, upload_pdf, settings)
    settings.processed_folder.mkdir(parents=True, exist_ok=True)
    final_path = settings.processed_folder / upload_pdf.name
    if final_path.exists():
        final_path.unlink()
    shutil.move(str(upload_pdf), final_path)
    print(f"Complete. Moved to: {final_path}")


class QuoteApprovalHandler:
    def __init__(self, settings: Settings):
        self.settings = settings

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".pdf":
            return
        if path.name.lower() == self.settings.renamed_pdf.lower():
            return
        try:
            process_pdf(path, self.settings)
        except Exception as exc:
            print(f"ERROR processing {path}: {exc}")
            self.settings.error_folder.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(path), self.settings.error_folder / path.name)
            except Exception:
                pass


def watch(settings: Settings) -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    global QuoteApprovalHandler
    if not issubclass(QuoteApprovalHandler, FileSystemEventHandler):
        class _QuoteApprovalHandler(QuoteApprovalHandler, FileSystemEventHandler):
            pass
        QuoteApprovalHandler = _QuoteApprovalHandler
    settings.watch_folder.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(QuoteApprovalHandler(settings), str(settings.watch_folder), recursive=False)
    observer.start()
    print(f"Watching: {settings.watch_folder}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def main() -> None:
    parser = argparse.ArgumentParser(description="TIM Quote Approval Automation v1")
    parser.add_argument("--pdf", type=Path, help="Process one PDF immediately")
    parser.add_argument("--watch", action="store_true", help="Watch folder from .env")
    parser.add_argument("--parse-only", action="store_true", help="Only parse and print WO/PO; do not use browser")
    args = parser.parse_args()

    settings = load_settings()
    if args.pdf:
        text = extract_pdf_text(args.pdf)
        wo_po = extract_wo_or_po(text)
        print(f"Found WO/PO: {wo_po}")
        if not args.parse_only:
            process_pdf(args.pdf, settings)
    elif args.watch:
        watch(settings)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
