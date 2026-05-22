import fitz
from pathlib import Path
from bs4 import BeautifulSoup


def extract_text(file_path: Path) -> str:
    file_path = Path(file_path)

    if file_path.suffix.lower() in [".htm", ".html"]:
        html = file_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text("\n")

    doc = fitz.open(file_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text