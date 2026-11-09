import csv
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


class ExtractionError(RuntimeError):
    pass


def extract_pages(path: Path) -> list[tuple[int | None, str]]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            return [(index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)]
        if suffix == ".docx":
            doc = DocxDocument(str(path))
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
            return [(None, text)]
        if suffix in {".txt", ".md"}:
            return [(None, path.read_text(encoding="utf-8-sig", errors="replace"))]
        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                text = "\n".join(", ".join(row) for row in csv.reader(file))
            return [(None, text)]
    except Exception as exc:
        raise ExtractionError("The uploaded file could not be extracted") from exc
    raise ExtractionError("Unsupported document format")
