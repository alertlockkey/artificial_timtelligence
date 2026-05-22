import re
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv
import os

from nest_isp_upload import upload_to_nest, archive_files
from boss_upload import boss_upload, parse_boss_invoice_name
from ts_upload import ts_upload, parse_true_source_invoice_name

load_dotenv()

WATCH_FOLDER = Path(os.getenv("DROPBOX_2015"))


# -----------------------------------------------------------------------------
# TRUE SOURCE
# -----------------------------------------------------------------------------

processed_ts = set()


def find_true_source_ready_invoices():
    """
    Find True Source invoice PDFs in the 2015 folder.

    Expected filename:
        trip_no-po_no- INVOICE - LOCATION NAME WO# wo_no INV# inv_no.pdf

    Example:
        1-05236609- INVOICE - FAMILY DOLLAR WO# 03442788 INV# 56898.pdf
    """
    invoices = sorted(WATCH_FOLDER.glob("*- INVOICE - * WO# * INV# *.pdf"))
    ready = []

    for invoice_pdf in invoices:
        try:
            data = parse_true_source_invoice_name(invoice_pdf)
        except ValueError:
            continue

        key = (data["po_no"], data["wo_no"], data["inv_no"])

        if key in processed_ts:
            continue

        ready.append((key, invoice_pdf, data))

    return ready


def process_true_source_invoices():
    ready_invoices = find_true_source_ready_invoices()

    for key, invoice_pdf, data in ready_invoices:
        po_no = data["po_no"]
        wo_no = data["wo_no"]
        inv_no = data["inv_no"]

        print(f"Uploading True Source invoice for PO {po_no}, WO {wo_no}, INV {inv_no}")

        try:
            ts_upload(invoice_pdf)
            processed_ts.add(key)
            print(f"True Source upload completed for PO {po_no}, WO {wo_no}, INV {inv_no}")

        except Exception as e:
            print(f"True Source upload failed for PO {po_no}, WO {wo_no}, INV {inv_no}: {e}")


# -----------------------------------------------------------------------------
# BOSS
# -----------------------------------------------------------------------------

processed_boss = set()


def find_boss_ready_package():
    invoices = list(WATCH_FOLDER.glob("INV Boss Facility WO# * INV# *.pdf"))
    photos = sorted(WATCH_FOLDER.glob("boss*.jpg"))

    if not invoices:
        return None

    if len(photos) < 3:
        print("Waiting for at least 3 Boss photos...")
        return None

    invoice_pdf = invoices[0]
    wo_no, inv_no = parse_boss_invoice_name(invoice_pdf)

    key = (wo_no, inv_no)

    if key in processed_boss:
        return None

    return {
        "key": key,
        "invoice_pdf": invoice_pdf,
        "photos": photos,
        "wo_no": wo_no,
        "inv_no": inv_no,
    }


def process_boss_package():
    package = find_boss_ready_package()

    if not package:
        return

    wo_no = package["wo_no"]
    inv_no = package["inv_no"]

    print(f"Uploading Boss invoice for WO {wo_no}, INV {inv_no}")

    invoice_data = {
        "wo_no": wo_no,
        "inv_no": inv_no,
        "invoice_date": "05/20/2026",

        "labor_qty": "2",
        "labor_rate": "95.00",

        "travel_qty": "1",
        "travel_rate": "150.00",

        "material_qty": "1",
        "material_total": "105.90",
    }

    try:
        boss_upload(package["invoice_pdf"], invoice_data)
        processed_boss.add(package["key"])
        print(f"Boss upload completed for WO {wo_no}, INV {inv_no}")

    except Exception as e:
        print(f"Boss upload failed for WO {wo_no}, INV {inv_no}: {e}")


# -----------------------------------------------------------------------------
# NEST
# -----------------------------------------------------------------------------

PATTERN = re.compile(
    r"^(INV|WO) Nest WO# (?P<wo_no>.+?) INV# (?P<inv_no>.+?)\.pdf$",
    re.IGNORECASE,
)

processed_pairs = set()


def find_ready_pairs():
    files = list(WATCH_FOLDER.glob("*.pdf"))
    grouped = {}

    for file in files:
        match = PATTERN.match(file.name)
        if not match:
            continue

        doc_type = match.group(1).upper()
        wo_no = match.group("wo_no").strip()
        inv_no = match.group("inv_no").strip()

        key = (wo_no, inv_no)

        grouped.setdefault(key, {})
        grouped[key][doc_type] = file

    ready = []

    for key, docs in grouped.items():
        if "INV" in docs and "WO" in docs and key not in processed_pairs:
            ready.append((key, docs["INV"], docs["WO"]))

    return ready


def process_ready_pairs():
    ready_pairs = find_ready_pairs()

    for key, invoice_pdf, signoff_pdf in ready_pairs:
        wo_no, inv_no = key

        print(f"Uploading Nest ISP docs for WO {wo_no}, INV {inv_no}")

        try:
            upload_to_nest(invoice_pdf, signoff_pdf, wo_no)
            archive_folder = archive_files([invoice_pdf, signoff_pdf])
            processed_pairs.add(key)

            print(f"Success. Moved files to {archive_folder}")

        except Exception as e:
            print(f"Failed upload for WO {wo_no}, INV {inv_no}: {e}")


# -----------------------------------------------------------------------------
# WATCHER
# -----------------------------------------------------------------------------

def process_all_portals():
    process_ready_pairs()
    process_boss_package()
    process_true_source_invoices()


class FolderWatcher(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            time.sleep(2)
            process_all_portals()

    def on_modified(self, event):
        if not event.is_directory:
            time.sleep(2)
            process_all_portals()


if __name__ == "__main__":
    print(f"Watching folder: {WATCH_FOLDER}")

    process_all_portals()

    observer = Observer()
    observer.schedule(FolderWatcher(), str(WATCH_FOLDER), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
