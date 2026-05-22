import time
import shutil
import json
import pdfkit
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from parser_router import parse_po
from service_fusion_bot import fill_service_fusion_job

def convert_htm_to_pdf(htm_path: Path, output_folder: Path) -> Path:
    pdf_path = output_folder / f"{htm_path.stem}.pdf"

    try:
        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )

        pdfkit.from_file(
            str(htm_path),
            str(pdf_path),
            configuration=config
        )

        print(f"Converted to PDF: {pdf_path.name}")
        return pdf_path

    except Exception as e:
        print(f"PDF conversion failed: {e}")
        return None

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

        file_path = Path(event.src_path)

        ALLOWED_EXTENSIONS = [".pdf", ".htm", ".html"]

        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return

        print(f"New PO detected: {file_path.name}")

        # Give Dropbox/Windows time to finish writing the file
        time.sleep(3)

        try:
            job_data = parse_po(file_path)
            print(json.dumps(job_data, indent=2))

            fill_service_fusion_job(job_data)

            # Convert HTM to PDF if applicable
            if file_path.suffix.lower() in [".htm", ".html"]:
                pdf_file = convert_htm_to_pdf(file_path, PROCESSED)

                if pdf_file:
                    # Delete original HTM after conversion
                    file_path.unlink()
                else:
                    # fallback: move original if conversion fails
                    shutil.move(str(file_path), PROCESSED / file_path.name)

            else:
                shutil.move(str(file_path), PROCESSED / file_path.name)
            print(f"Processed: {file_path.name}")

        except Exception as e:
            print(f"Failed processing {file_path.name}: {e}")
            shutil.move(str(file_path), FAILED / file_path.name)


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