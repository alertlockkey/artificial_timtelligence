# service_fusion_update.py

import os
import time
from pathlib import Path
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

load_dotenv()

SERVICE_FUSION_LOGIN_URL = "https://admin.servicefusion.com"
SERVICE_FUSION_JOBS_URL = "https://admin.servicefusion.com/jobs/"

SF_COMPANY_ID = (
    os.getenv("SERVICE_FUSION_COMPANY_ID")
    or os.getenv("SF_COMPANY_ID")
)
SF_USERNAME = (
    os.getenv("SERVICE_FUSION_USERNAME")
    or os.getenv("SF_USERNAME")
)
SF_PASSWORD = (
    os.getenv("SERVICE_FUSION_PASSWORD")
    or os.getenv("SF_PASSWORD")
)


def money_with_commas(amount):
    return f"${float(str(amount).replace(',', '').replace('$', '')):,.2f}"


def build_ts_note(invoice_data, archived_file: Path):
    return (
        f"INVOICE {invoice_data['inv_no']} {money_with_commas(invoice_data['invoice_amount'])}\n"
        f"{archived_file.name} IN 2015\n"
        "INVOICE SUBMITTED THROUGH TS PORTAL"
    )


def wait_for(driver, by, selector, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, selector))
    )


def click_when_ready(driver, by, selector, timeout=20):
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, selector))
    )
    element.click()
    return element


def js_set_value(driver, selector, value):
    script = """
    const el = document.querySelector(arguments[0]);
    if (!el) throw new Error('Element not found: ' + arguments[0]);

    el.value = arguments[1];
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));

    if (window.jQuery) {
        window.jQuery(el).val(arguments[1]).trigger('change');
    }
    """
    driver.execute_script(script, selector, value)




def select2_single_by_text(driver, select_id, visible_text):
    """Set a Service Fusion Select2/native select by visible option text."""
    script = """
    const select = document.getElementById(arguments[0]);
    const text = arguments[1];
    if (!select) throw new Error('Select not found: ' + arguments[0]);

    let foundValue = '';
    [...select.options].forEach(opt => {
        if (opt.text.trim().toLowerCase() === text.trim().toLowerCase()) {
            foundValue = opt.value;
        }
    });

    if (!foundValue) {
        throw new Error('Option not found in #' + arguments[0] + ': ' + text);
    }

    if (window.jQuery) {
        window.jQuery(select).val(foundValue).trigger('change');
    } else {
        select.value = foundValue;
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    """
    driver.execute_script(script, select_id, visible_text)


def is_logged_in(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "a[href*='/jobs/jobsAdd'], #customer_name, input[placeholder*='Search'], input[aria-label*='Search']"
            ))
        )
        return True
    except TimeoutException:
        return False


def fill_first_matching(driver, selectors, value):
    for selector in selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        visible_elements = [el for el in elements if el.is_displayed()]
        if visible_elements:
            field = visible_elements[0]
            field.clear()
            field.send_keys(value)
            return True
    return False


def login_to_service_fusion(driver):
    """
    Login structure copied from the working Service Fusion bot pattern.
    Uses the company ID, username, and password fields instead of assuming a
    two-field login screen.
    """
    driver.get(SERVICE_FUSION_LOGIN_URL)
    time.sleep(2)

    if is_logged_in(driver):
        print("Already logged into Service Fusion.")
        return

    if not all([SF_COMPANY_ID, SF_USERNAME, SF_PASSWORD]):
        raise RuntimeError(
            "Missing Service Fusion credentials. Expected SERVICE_FUSION_COMPANY_ID/SF_COMPANY_ID, "
            "SERVICE_FUSION_USERNAME/SF_USERNAME, and SERVICE_FUSION_PASSWORD/SF_PASSWORD in .env."
        )

    possible_company_fields = [
        "input[name='company']",
        "input[name='companyId']",
        "input[name='company_id']",
        "input[id*='company']",
    ]

    possible_username_fields = [
        "input[name='username']",
        "input[name='uid']",
        "input[id*='username']",
        "input[id*='uid']",
    ]

    possible_password_fields = [
        "input[type='password']",
        "input[name='password']",
    ]

    if not fill_first_matching(driver, possible_company_fields, SF_COMPANY_ID):
        raise RuntimeError("Could not find Service Fusion company ID field.")

    if not fill_first_matching(driver, possible_username_fields, SF_USERNAME):
        raise RuntimeError("Could not find Service Fusion username field.")

    if not fill_first_matching(driver, possible_password_fields, SF_PASSWORD):
        raise RuntimeError("Could not find Service Fusion password field.")

    buttons = driver.find_elements(
        By.CSS_SELECTOR,
        "button[type='submit'], input[type='submit'], button"
    )

    for button in buttons:
        if not button.is_displayed():
            continue

        text = button.text.lower().strip()
        value = (button.get_attribute("value") or "").lower().strip()

        if "login" in text or "log in" in text or "sign in" in text or "login" in value:
            button.click()
            break
    else:
        raise RuntimeError("Could not find Service Fusion login button.")

    WebDriverWait(driver, 30).until(
        lambda d: "login" not in d.current_url.lower()
    )
    time.sleep(2)


def open_global_search_result_by_po(driver, po_no: str):
    """
    Search Service Fusion by PO number and open the matching job.

    This mirrors the working true_source_approval_bot.py flow:
      1. Go directly to /jobs/
      2. Use the Kendo Global Search input
      3. Type the PO and press Enter
      4. Click the visible result containing the PO
    """
    driver.get(SERVICE_FUSION_JOBS_URL)
    time.sleep(2)

    global_search_selectors = [
        'div.search-container input[kendosearchbar][placeholder="Global Search"]',
        'input[kendosearchbar][placeholder="Global Search"]',
        'input[placeholder="Global Search"]',
        'input[placeholder*="Global Search"]',
        '#k-92e3ae7c-f953-4282-8649-ae91a5ed2d66',
    ]

    search_box = None
    last_error = None

    for selector in global_search_selectors:
        try:
            search_box = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            if search_box and search_box.is_displayed():
                break
        except Exception as exc:
            last_error = exc
            search_box = None

    if not search_box:
        raise RuntimeError(f"Could not find Service Fusion Global Search input. Last error: {last_error}")

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_box)
    time.sleep(0.5)
    search_box.click()
    time.sleep(0.2)
    search_box.send_keys(Keys.CONTROL, "a")
    search_box.send_keys(Keys.BACKSPACE)
    search_box.send_keys(po_no)
    time.sleep(1.5)

    # Service Fusion's Kendo global search usually requires choosing the
    # autocomplete result. Press ArrowDown + Enter first, then fall back to
    # clicking visible result text if needed.
    opened_job = False

    try:
        search_box.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.5)
        search_box.send_keys(Keys.ENTER)
        time.sleep(3)

        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "#jobNo, #job-view-master-status, button[onclick*='add-new-note']"
            ))
        )
        opened_job = True

    except TimeoutException:
        opened_job = False

    if not opened_job:
        try:
            # Select matching Global Search result
            result_selector = "sf-global-search-results-list-job"

            result = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, result_selector))
            )

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", result)
            time.sleep(0.5)
            result.click()

            time.sleep(3)
        except TimeoutException as exc:
            raise RuntimeError(f"Could not open Service Fusion job result for PO {po_no}.") from exc

    time.sleep(1)

    # Final confirmation that a job detail page loaded.
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#jobNo, #job-view-master-status, button[onclick*='add-new-note']"))
        )
    except TimeoutException:
        print("WARNING: PO result was clicked, but job detail markers were not found yet.")

def add_note_to_job(driver, note_text: str):
    """Add a note using the same Service Fusion selectors as true_source_approval_bot.py."""
    # Click Add Notes.
    try:
        add_notes_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick*='add-new-note']"))
        )
    except TimeoutException:
        add_notes_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(normalize-space(), 'Add Notes') or contains(normalize-space(), 'Add Note')]"))
        )

    add_notes_button.click()
    time.sleep(1)

    note_box = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#add-new-note"))
    )
    note_box.click()
    note_box.clear()
    note_box.send_keys(note_text)

    save_note_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#add-new-note-btn"))
    )
    save_note_button.click()
    time.sleep(2)

def set_job_status_completed(driver):
    # Click/open the inline Current Status editor if needed
    try:
        status_trigger = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#job-view-master-status, #xedit-job_status"))
        )
        status_trigger.click()
        time.sleep(1)
    except TimeoutException:
        pass

    status_select = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "#tab-details select.input-medium, "
            "#tab-details > div:nth-child(1) > div.span7.borders > div > "
            "span.editable-container.editable-inline > div > form > div > "
            "div:nth-child(1) > div > select"
        ))
    )

    # Select Completed by visible text/value
    for option in status_select.find_elements(By.TAG_NAME, "option"):
        if option.text.strip().lower() == "completed":
            option.click()
            break
    else:
        raise RuntimeError("Could not find Completed option in status dropdown.")

    time.sleep(1)

    # Submit inline editable status form
    try:
        submit_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                ".editable-container button[type='submit'], "
                ".editable-buttons button[type='submit'], "
                ".editable-container i.icon-ok"
            ))
        )
        submit_btn.click()
    except TimeoutException:
        status_select.send_keys(Keys.ENTER)

    # Page refreshes after status update
    time.sleep(4)

def save_job_update(driver):
    """Save the job using the same bottom Save Job button flow as service_fusion_bot.py."""
    time.sleep(2)

    save_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "createjobbottom"))
    )

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_button)
    time.sleep(2)
    save_button.click()
    time.sleep(3)


def update_service_fusion_after_ts(invoice_data, archived_file: Path):
    note_text = build_ts_note(invoice_data, archived_file)
    po_no = invoice_data["po_no"]

    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument(r"--user-data-dir=C:\ServiceFusionAutomation\ChromeProfile")

    driver = webdriver.Chrome(options=chrome_options)
    driver.maximize_window()

    try:
        login_to_service_fusion(driver)
        open_global_search_result_by_po(driver, po_no)
        add_note_to_job(driver, note_text)
        set_job_status_completed(driver)
        print(f"Service Fusion updated for PO {po_no}.")
    finally:
        driver.quit()
