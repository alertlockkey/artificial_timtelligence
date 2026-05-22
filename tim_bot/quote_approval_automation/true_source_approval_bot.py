# true_source_approval_bot.py
"""
TIM - True Source Quote Approval / New PO Automation

Flow:
1. Watch quote_approval_emails folder for a True Source New Purchase Order email PDF.
2. Parse WO, new PO, previous PO, and trip number.
3. Rename PDF to WO-########_Quote Approval Email.pdf.
4. Log into Service Fusion.
5. Find original job by initial_po.
6. Copy job, add notes, update PO #, upload approval email, update copied job title, save.

Required .env:
    SERVICE_FUSION_COMPANY_ID=company
    SERVICE_FUSION_USERNAME=username
    SERVICE_FUSION_PASSWORD=password
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import re
import shutil
import time
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from dotenv import load_dotenv
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

WATCH_FOLDER = Path("quote_approval_emails")
PROCESSED_FOLDER = WATCH_FOLDER / "_processed"
FAILED_FOLDER = WATCH_FOLDER / "_failed"
SERVICE_FUSION_JOBS_URL = "https://admin.servicefusion.com/jobs/"

SEPARATOR_NOTE = """***   COPIED JOB  -  NEW NOTES START HERE  ***

***   COPIED JOB  -  NEW NOTES START HERE  ***"""

QUOTE_APPROVAL_NOTE = """QUOTE APPROVED
APPROVAL EMAIL IN DOCS"""


@dataclasses.dataclass
class TrueSourceApproval:
    pdf_path: Path
    wo_no: str
    po_no: str
    initial_po: str
    trip_no: int
    renamed_pdf_path: Path

    @property
    def sf_po_number(self) -> str:
        return f"{self.wo_no}---{self.trip_no}-{self.po_no}"

    @property
    def renamed_filename(self) -> str:
        return f"WO-{self.wo_no}_Quote Approval Email.pdf"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_pdf_text(pdf_path: Path) -> str:
    with fitz.open(pdf_path) as doc:
        return "\n".join(page.get_text("text") for page in doc)


def parse_true_source_pdf(pdf_path: Path) -> TrueSourceApproval:
    """
    Expected True Source wording examples:
      "new additional Purchase Order PO-05238114 on Work Order WO-03426984"
      "New [05/20/2026] Purchase Order, PO-05238114:"
      "Previous [05/11/2026] Purchase Order, PO-05216980 :"

    Trip logic:
      trip_no = number of Previous Purchase Order entries + 1.
      Example: one Previous PO means current trip is 2.
    """
    text = extract_pdf_text(pdf_path)

    wo_match = re.search(r"\bWork\s+Order\s+WO[-\s]?(\d{6,})\b", text, re.I)
    if not wo_match:
        wo_match = re.search(r"\bSummary\s+of\s+WO[-\s]?(\d{6,})\b", text, re.I)
    if not wo_match:
        all_wos = re.findall(r"\bWO[-\s]?(\d{6,})\b", text, re.I)
        if not all_wos:
            raise ValueError(f"Could not find Work Order number in {pdf_path}")
        wo_no = all_wos[0]
    else:
        wo_no = wo_match.group(1)

    new_po_match = re.search(r"\bNew\s*\[[^\]]+\]\s*Purchase\s+Order,\s*PO[-\s]?(\d{6,})", text, re.I)
    if not new_po_match:
        new_po_match = re.search(r"\bnew\s+additional\s+Purchase\s+Order\s+PO[-\s]?(\d{6,})", text, re.I)
    if not new_po_match:
        raise ValueError(f"Could not find New Purchase Order number in {pdf_path}")
    po_no = new_po_match.group(1)

    previous_pos = re.findall(r"\bPrevious\s*\[[^\]]+\]\s*Purchase\s+Order,\s*PO[-\s]?(\d{6,})", text, re.I)
    if not previous_pos:
        raise ValueError(f"Could not find Previous Purchase Order number in {pdf_path}")

    initial_po = previous_pos[0]
    trip_no = len(previous_pos) + 1
    renamed_pdf_path = pdf_path.with_name(f"WO-{wo_no}_Quote Approval Email.pdf")

    return TrueSourceApproval(pdf_path, wo_no, po_no, initial_po, trip_no, renamed_pdf_path)


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for n in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{n}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find unique filename for {path}")


def rename_pdf_for_docs(data: TrueSourceApproval) -> TrueSourceApproval:
    target = ensure_unique_path(data.renamed_pdf_path)
    if data.pdf_path.resolve() != target.resolve():
        shutil.move(str(data.pdf_path), str(target))
    return dataclasses.replace(data, pdf_path=target, renamed_pdf_path=target)


def load_required_env() -> tuple[str, str, str]:
    load_dotenv()
    company = os.getenv("SERVICE_FUSION_COMPANY_ID", "").strip()
    username = os.getenv("SERVICE_FUSION_USERNAME", "").strip()
    password = os.getenv("SERVICE_FUSION_PASSWORD", "").strip()
    missing = [name for name, value in [("SERVICE_FUSION_COMPANY_ID", company), ("SERVICE_FUSION_USERNAME", username), ("SERVICE_FUSION_PASSWORD", password)] if not value]
    if missing:
        raise RuntimeError(f"Missing required .env values: {', '.join(missing)}")
    return company, username, password


def fill_first_visible(page: Page, selectors: list[str], value: str, timeout: int = 5000) -> None:
    last_error: Optional[Exception] = None
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.fill(value)
            return
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not fill any selector from {selectors}") from last_error


def click_first_visible(page: Page, selectors: list[str], timeout: int = 5000) -> None:
    last_error: Optional[Exception] = None
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            return
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not click any selector from {selectors}") from last_error


def login_service_fusion(page: Page) -> None:
    company, username, password = load_required_env()
    page.goto("https://admin.servicefusion.com/", wait_until="domcontentloaded")
    fill_first_visible(page, ['input[name="company"]', 'input[name="companyId"]', 'input[name="company_id"]', 'input[placeholder*="Company" i]', 'input[placeholder*="Account" i]', '#company', '#companyId'], company)
    fill_first_visible(page, ['input[name="username"]', 'input[name="email"]', 'input[type="email"]', 'input[placeholder*="User" i]', 'input[placeholder*="Email" i]', '#username', '#email'], username)
    fill_first_visible(page, ['input[name="password"]', 'input[type="password"]', '#password'], password)
    click_first_visible(page, ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("Login")', 'button:has-text("Sign In")', 'input[value*="Login" i]', 'input[value*="Sign" i]'])
    page.wait_for_load_state("networkidle", timeout=5000)


def global_search_job(page: Page, query: str) -> None:
    page.goto(SERVICE_FUSION_JOBS_URL, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=5000)
    search = page.locator('div.search-container input[kendosearchbar][placeholder="Global Search"]').first
    try:
        search.wait_for(state="visible", timeout=5000)
    except PlaywrightTimeoutError:
        search = page.locator('input[kendosearchbar][placeholder="Global Search"], input[placeholder="Global Search"]').first
        search.wait_for(state="visible", timeout=5000)
    search.click()
    search.fill(query)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1500)
    result = page.locator(f'text="{query}"').first
    result.wait_for(state="visible", timeout=5000)
    result.click()
    page.wait_for_load_state("networkidle", timeout=5000)


def get_job_title(page: Page) -> str:
    loc = page.locator("#jobNo").first
    loc.wait_for(state="visible", timeout=5000)
    return clean_text(loc.inner_text())


def get_job_status(page: Page) -> str:
    status = page.locator("#job-view-master-status").first
    try:
        status.wait_for(state="visible", timeout=5000)
        return clean_text(status.inner_text())
    except Exception:
        return ""


def copy_job(page: Page) -> None:
    click_first_visible(page, ['button.dropdown-toggle:has-text("More")', 'button:has-text("More")'])
    click_first_visible(page, ['a:has-text("Copy Job")', 'a[onclick^="copyJob"]'])
    click_first_visible(page, ['button.jquery-msgbox-button-submit:has-text("Copy")', 'button:has-text("Copy")'], timeout=15000)
    page.wait_for_load_state("networkidle", timeout=5000)
    page.locator("#jobNo").first.wait_for(state="visible", timeout=5000)


def add_note(page: Page, note_text: str) -> None:
    click_first_visible(page, ['button:has-text("Add Notes")', 'button[onclick*="add-new-note"]'])
    note = page.locator("#add-new-note")
    note.wait_for(state="visible", timeout=5000)
    note.click()
    note.fill(note_text)
    page.locator("#add-new-note-btn").click()
    page.wait_for_timeout(1000)


def submit_xeditable_text(page: Page, trigger_selector: str, new_value: str) -> None:
    page.locator(trigger_selector).first.wait_for(state="visible", timeout=5000)
    page.locator(trigger_selector).first.click()
    inp = page.locator(".editable-container input.input-medium, .editable-input input.input-medium, input.input-medium").first
    inp.wait_for(state="visible", timeout=5000)
    inp.fill(new_value)
    click_first_visible(page, ['.editable-container button[type="submit"]', '.editable-buttons button[type="submit"]', '.editable-container i.icon-ok', 'i.icon-ok.icon-white'])
    page.wait_for_timeout(1000)


def update_po_number(page: Page, po_number: str) -> None:
    submit_xeditable_text(page, "#xedit-job_po_number", po_number)


def update_job_title(page: Page, new_title: str) -> None:
    submit_xeditable_text(page, "#jobNo", new_title)


def close_upload_popup(page: Page) -> None:
    close_btn = page.locator("#upload-close").first
    try:
        if close_btn.is_visible(timeout=5000):
            close_btn.click()
            page.wait_for_timeout(500)
    except Exception:
        # Some uploads may auto-close or render the close button differently.
        # Do not fail the whole run if there is no popup to close.
        pass


def upload_doc(page: Page, pdf_path: Path) -> None:
    page.locator("#documents-title").click()
    page.wait_for_timeout(1000)
    page.locator("#add-new-doc-btn").wait_for(state="visible", timeout=3000)
    page.locator("#add-new-doc-btn").click()
    input_file = page.locator('input[type="file"]').first
    try:
        input_file.wait_for(state="attached", timeout=5000)
        input_file.set_input_files(str(pdf_path))
    except Exception:
        with page.expect_file_chooser() as fc_info:
            page.locator("#plupload-demo-box_browse, a.plupload_add").first.click()
        fc_info.value.set_files(str(pdf_path))
    page.locator("a.plupload_start").wait_for(state="visible", timeout=3000)
    page.locator("a.plupload_start").click()
    page.wait_for_timeout(3000)

    # Close the Upload Document popup before continuing.
    # If the modal stays open, it can block the job title edit and Save Job button.
    close_upload_popup(page)


def save_job(page: Page) -> None:
    page.locator("#createjobbottom").wait_for(state="visible", timeout=3000)
    page.locator("#createjobbottom").click()
    page.wait_for_load_state("networkidle", timeout=3000)


def process_true_source_pdf(pdf_path: Path, headless: bool = False, parse_only: bool = False) -> None:
    data = parse_true_source_pdf(pdf_path)
    print("Parsed True Source approval:")
    print(f"  WO:         {data.wo_no}")
    print(f"  New PO:     {data.po_no}")
    print(f"  Initial PO: {data.initial_po}")
    print(f"  Trip #:     {data.trip_no}")
    print(f"  SF PO #:    {data.sf_po_number}")
    print(f"  Rename to:  {data.renamed_filename}")
    if parse_only:
        return

    data = rename_pdf_for_docs(data)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        login_service_fusion(page)
        print(f"Searching Service Fusion by initial PO {data.initial_po}...")
        global_search_job(page, data.initial_po)
        job_title = get_job_title(page)
        print(f"Original job title: {job_title}")
        status = get_job_status(page)
        if status:
            print(f"Original job status: {status}")
            if status.lower() not in {"complete", "completed"}:
                print("WARNING: Original job does not appear to be Complete/Completed. Continuing for now.")
        print("Copying job...")
        copy_job(page)
        print("Adding copied-job separator note...")
        add_note(page, SEPARATOR_NOTE)
        print("Adding quote approval note...")
        add_note(page, QUOTE_APPROVAL_NOTE)
        print(f"Updating PO # to {data.sf_po_number}...")
        update_po_number(page, data.sf_po_number)
        print(f"Uploading {data.renamed_pdf_path.name}...")
        upload_doc(page, data.renamed_pdf_path)
        new_title = f"{job_title}-{data.trip_no}"
        print(f"Updating copied job title to {new_title}...")
        update_job_title(page, new_title)
        print("Saving job...")
        save_job(page)
        context.close()
        browser.close()

    PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)
    if data.renamed_pdf_path.exists():
        shutil.move(str(data.renamed_pdf_path), str(ensure_unique_path(PROCESSED_FOLDER / data.renamed_pdf_path.name)))
    print("Done.")


def wait_until_file_is_stable(path: Path, checks: int = 3, delay: float = 1.0) -> bool:
    last_size = -1
    stable_count = 0
    for _ in range(checks + 5):
        if not path.exists():
            return False
        size = path.stat().st_size
        if size == last_size and size > 0:
            stable_count += 1
            if stable_count >= checks:
                return True
        else:
            stable_count = 0
            last_size = size
        time.sleep(delay)
    return False


def watch_folder(headless: bool = False, poll_seconds: int = 3) -> None:
    WATCH_FOLDER.mkdir(exist_ok=True)
    PROCESSED_FOLDER.mkdir(exist_ok=True)
    FAILED_FOLDER.mkdir(exist_ok=True)
    print(f"Watching folder: {WATCH_FOLDER.resolve()}")
    while True:
        for pdf_path in sorted(WATCH_FOLDER.glob("*.pdf")):
            try:
                if not wait_until_file_is_stable(pdf_path):
                    continue
                process_true_source_pdf(pdf_path, headless=headless)
            except Exception as exc:
                print(f"FAILED: {pdf_path.name}: {exc}")
                try:
                    shutil.move(str(pdf_path), str(ensure_unique_path(FAILED_FOLDER / pdf_path.name)))
                except Exception:
                    pass
        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, help="Path to a True Source New PO email PDF.")
    parser.add_argument("--watch", action="store_true", help="Watch quote_approval_emails folder.")
    parser.add_argument("--parse-only", action="store_true", help="Only parse and print PDF data.")
    parser.add_argument("--headless", action="store_true", help="Run browser headless.")
    args = parser.parse_args()
    if not args.pdf and not args.watch:
        parser.error("Use --pdf path/to/file.pdf or --watch")
    if args.pdf:
        process_true_source_pdf(args.pdf, headless=args.headless, parse_only=args.parse_only)
    if args.watch:
        watch_folder(headless=args.headless)


if __name__ == "__main__":
    main()
