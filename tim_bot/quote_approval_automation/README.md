# Quote Approval Automation v1

This watches a folder for quote approval email PDFs, extracts the WO/PO number, renames the PDF to `Quote Approval Email.pdf`, opens Service Fusion, searches the WO/PO, edits the job, sets status/tech/note, uploads the PDF to Docs, and saves the job.

## Setup

```bash
cd quote_approval_automation_v1
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
```

Edit `.env` with your watch folder and Service Fusion credentials. This version uses the same login variable names as `service_fusion_po_automation`:

```env
SERVICE_FUSION_COMPANY_ID=company
SERVICE_FUSION_USERNAME=username
SERVICE_FUSION_PASSWORD=password
```

## Run once against a sample PDF

```bash
python quote_approval_bot.py --pdf "C:\path\to\approval.pdf"
```

## Watch the folder

```bash
python quote_approval_bot.py --watch
```

## Notes

- The Service Fusion search input ID changes, so this script uses stable attributes like `placeholder="Global Search"` instead of the dynamic ID.
- The upload control is powered by Plupload, so the script tries the visible Add Files button first, then falls back to any available `<input type="file">`.
- Keep `HEADLESS=0` during training so you can watch TIM and tweak selectors if Service Fusion behaves differently.


## Service Fusion login

The login flow now expects the normal Service Fusion Company ID / Username / Password form and reads:

- `SERVICE_FUSION_COMPANY_ID`
- `SERVICE_FUSION_USERNAME`
- `SERVICE_FUSION_PASSWORD`

If TIM is already logged in during a reused/browser session, the login function safely skips the form.


## v1.2 update

Global Search now targets the stable Kendo search wrapper/input instead of the dynamic generated input id. Primary selector:

```css
div.search-container input[kendosearchbar][placeholder="Global Search"]
```

Fallbacks are included for `kendo-autocomplete`, `role="combobox"`, and plain `placeholder="Global Search"`.


## v1.4 update

Step 11 now targets the stable note textarea `#add-new-note`, waits for it to become visible after clicking Add Notes, and fills `QUOTE APPROVAL IN DOCS` by default.

## v1.6 update

- Step 8 now updates Current Status through Service Fusion's inline editable status control (`#statusManual`) instead of Select2.
- `Dispatched` is selected by exact option value `1018710314` to avoid accidentally selecting `To Do Lists`.
- After Start upload, TIM now clicks `#upload-close` to close the upload modal before clicking Save Job.
