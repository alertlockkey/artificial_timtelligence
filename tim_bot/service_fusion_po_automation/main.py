import time
import shutil
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from parser_router import parse_po
from service_fusion_bot import fill_service_fusion_job


BASE_DIR = Path(__file__).parent
INCOMING = BASE_DIR / "incoming_pos"
PROCESSED = BASE_DIR / "processed_pos"
FAILED = BASE_DIR / "failed_pos"

for folder in [INCOMING, PROCESSED, FAILED]:
    folder.mkdir(exist_ok=True)


class POHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        pdf_path = Path(event.src_path)

        if pdf_path.suffix.lower() != ".pdf":
            return

        print(f"New PO detected: {pdf_path.name}")

        # Give Dropbox/Windows time to finish writing the file
        time.sleep(3)

        try:
            job_data = parse_po(pdf_path)
            print(json.dumps(job_data, indent=2))

            fill_service_fusion_job(job_data)

            shutil.move(str(pdf_path), PROCESSED / pdf_path.name)
            print(f"Processed: {pdf_path.name}")

        except Exception as e:
            print(f"Failed processing {pdf_path.name}: {e}")
            shutil.move(str(pdf_path), FAILED / pdf_path.name)


if __name__ == "__main__":
    print(f"Watching folder: {INCOMING}")

    observer = Observer()
    observer.schedule(POHandler(), str(INCOMING), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()