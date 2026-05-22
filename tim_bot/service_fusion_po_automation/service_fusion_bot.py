import time, os
from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

SERVICE_FUSION_LOGIN_URL = "https://admin.servicefusion.com"
SERVICE_FUSION_CREATE_JOB_URL = "https://admin.servicefusion.com/jobs/jobsAdd"

SF_COMPANY_ID = os.getenv("SERVICE_FUSION_COMPANY_ID")
SF_USERNAME = os.getenv("SERVICE_FUSION_USERNAME")
SF_PASSWORD = os.getenv("SERVICE_FUSION_PASSWORD")

DEFAULT_STATUS = "Dispatched"
DEFAULT_TECHS = [
    "Sean Flanagan",
]

DEFAULT_LINE_ITEMS = [
    "Service Call",
    "Labor 1 Man per hour Standard",
]

def is_logged_in(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/jobs/jobsAdd'], #customer_name"))
        )
        return True
    except TimeoutException:
        return False


def login_to_service_fusion(driver):
    driver.get(SERVICE_FUSION_LOGIN_URL)

    time.sleep(2)

    if is_logged_in(driver):
        return

    if not all([SF_COMPANY_ID, SF_USERNAME, SF_PASSWORD]):
        raise RuntimeError("Missing Service Fusion credentials in .env file.")

    # These selectors may need one-time adjustment after inspecting login page.
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

    def fill_first_matching(selectors, value):
        for selector in selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                elements[0].clear()
                elements[0].send_keys(value)
                return True
        return False

    fill_first_matching(possible_company_fields, SF_COMPANY_ID)
    fill_first_matching(possible_username_fields, SF_USERNAME)
    fill_first_matching(possible_password_fields, SF_PASSWORD)

    # Try common login button selectors
    buttons = driver.find_elements(
        By.CSS_SELECTOR,
        "button[type='submit'], input[type='submit'], button"
    )

    for button in buttons:
        text = button.text.lower().strip()
        value = (button.get_attribute("value") or "").lower().strip()

        if "login" in text or "log in" in text or "sign in" in text or "login" in value:
            button.click()
            break
    else:
        raise RuntimeError("Could not find login button.")

    WebDriverWait(driver, 30).until(
        lambda d: "login" not in d.current_url.lower()
    )

def js_set_value(driver, selector, value):
    if value is None:
        return

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


def wait_for(driver, by, selector, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, selector))
    )


def click_when_ready(driver, by, selector, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, selector))
    ).click()


def select2_single_by_text(driver, select_id, visible_text):
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


def select2_multi_by_text(driver, select_id, names):
    if not names:
        return

    script = """
    const select = document.getElementById(arguments[0]);
    const names = arguments[1].map(x => x.trim().toLowerCase());
    if (!select) throw new Error('Select not found: ' + arguments[0]);

    const values = [];
    [...select.options].forEach(opt => {
        if (names.includes(opt.text.trim().toLowerCase())) {
            values.push(opt.value);
        }
    });

    if (values.length !== names.length) {
        throw new Error('One or more tech names were not found.');
    }

    if (window.jQuery) {
        window.jQuery(select).val(values).trigger('change');
    } else {
        [...select.options].forEach(opt => {
            opt.selected = values.includes(opt.value);
        });
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    """
    driver.execute_script(script, select_id, names)


def select_customer(driver, customer_name):
    box = wait_for(driver, By.ID, "customer_name")
    box.clear()
    box.send_keys(customer_name)

    time.sleep(1.5)

    # Select first autocomplete result
    box.send_keys(Keys.ARROW_DOWN)
    box.send_keys(Keys.ENTER)

    time.sleep(2)

def save_job(driver):
    time.sleep(2)

    save_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "createjobbottom"))
    )

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_button)
    time.sleep(2)
    save_button.click()

def add_line_item_by_search(driver, item_name):
    click_when_ready(driver, By.CSS_SELECTOR, 'a[data-target="#job-charges"]')
    time.sleep(1)

    search = wait_for(driver, By.ID, "service-product-search-box")
    search.clear()
    search.send_keys(item_name)
    time.sleep(2)

    # Service Fusion uses an autocomplete list. Pressing ENTER often chooses top result.
    search.send_keys(Keys.ARROW_DOWN)
    search.send_keys(Keys.ENTER)

    time.sleep(2)


def fill_service_fusion_job(job_data: dict):
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument(r"--user-data-dir=C:\ServiceFusionAutomation\ChromeProfile")

    driver = webdriver.Chrome(options=chrome_options)
    driver.maximize_window()
    login_to_service_fusion(driver)

    driver.get(SERVICE_FUSION_CREATE_JOB_URL)

    wait_for(driver, By.ID, "customer_name")

    wait_for(driver, By.ID, "customer_name")

    # Customer
    select_customer(driver, job_data.get("customer", ""))

    # Service Location
    js_set_value(driver, "#nickname_new", job_data.get("location_name", ""))
    js_set_value(driver, "#street_1", job_data.get("street", ""))
    js_set_value(driver, "#street_2", job_data.get("suite", ""))
    js_set_value(driver, "#city", job_data.get("city", ""))
    js_set_value(driver, "#state", job_data.get("state", "TX"))
    js_set_value(driver, "#postal_code", job_data.get("zip", ""))

    # Job Description
    js_set_value(driver, "#description", job_data.get("job_description", ""))

    # PO #
    js_set_value(driver, "#job-po-number", job_data.get("po_number", ""))

    # Current Status
    status = job_data.get("current_status") or DEFAULT_STATUS
    select2_single_by_text(driver, "select_status", status)

    # Assigned Techs
    techs = job_data.get("assigned_techs") or DEFAULT_TECHS
    select2_multi_by_text(driver, "assigned-techs", techs)

    # Notes For Tech
    js_set_value(driver, "#notes-for-tech", job_data.get("notes_for_techs", ""))

    # Mark modified flags so Service Fusion recognizes changes
    js_set_value(driver, "#jobLocationModified", "1")
    js_set_value(driver, "#jobStatusModified", "1")
    js_set_value(driver, "#jobTechsModified", "1")
    js_set_value(driver, "#jobJobNotesModified", "1")

    # Products & Services
    for item in job_data.get("line_items", DEFAULT_LINE_ITEMS):
        try:
            add_line_item_by_search(driver, item)
        except Exception as e:
            print(f"Could not auto-add line item '{item}': {e}")
            input(f"Please manually add '{item}', then press ENTER...")

    # save_job(driver)
    print("TIM saved the job.")