"""Load source documents (PDF and TXT) with page-level provenance.

Each loaded document is returned as a dict:
    {
        "doc_id":      "building_code_structural",
        "source":      "building_code_structural.pdf",   # filename
        "file_name":   "building_code_structural.pdf",
        "title":       "BUILDSURE SAMPLE BUILDING CODE...",
        "doc_type":    "building_code" | "spec" | "inspection_report",
        "project_id":  "global" | "<project_id>",
        "scope":       "global" | "project",
        "pages":       [
            {"page_number": 1, "text": "Page 1 content..."},
            {"page_number": 2, "text": "Page 2 content..."},
        ],
        "page_count":  2,
        "text":        "<full document text>",
    }
"""
import io
import re
from pathlib import Path
from typing import BinaryIO, Optional, Union

from src.config import DOCS_DIR


class DocumentLoadError(ValueError):
    """Raised when a file cannot be parsed as a PDF."""

# Maps raw document header types to standardized labels
_DOC_TYPE_LABELS = {
    "building code": "building_code",
    "building_code": "building_code",
    "project specification": "spec",
    "specification": "spec",
    "spec": "spec",
    "inspection report": "inspection_report",
    "inspection": "inspection_report",
    "inspection_report": "inspection_report",
}


def _detect_doc_type(text: str, filename: str) -> str:
    """Read the 'Document type:' header; fall back to the filename prefix."""
    for line in text.splitlines()[:15]:
        lower_line = line.strip().lower()
        if lower_line.startswith("document type:") or lower_line.startswith("doc type:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in _DOC_TYPE_LABELS:
                return _DOC_TYPE_LABELS[value]
    name = filename.lower()
    if name.startswith("building_code") or "building_code" in name:
        return "building_code"
    if name.startswith("spec") or "specification" in name:
        return "spec"
    if name.startswith("inspection") or "inspection_report" in name:
        return "inspection_report"
    return "building_code"


def load_pdf(
    file_or_path: Union[str, Path, BinaryIO, bytes],
    filename: Optional[str] = None,
    project_id: str = "global",
    scope: str = "global",
    doc_type: Optional[str] = None,
) -> dict:
    """Parse a PDF document page-by-page using pypdf."""
    from pypdf import PdfReader

    if isinstance(file_or_path, (str, Path)):
        path = Path(file_or_path)
        filename = filename or path.name
        stream: Union[BinaryIO, Path] = path
    elif isinstance(file_or_path, bytes):
        stream = io.BytesIO(file_or_path)
        filename = filename or "uploaded_document.pdf"
    else:
        stream = file_or_path
        filename = filename or "uploaded_document.pdf"

    try:
        reader = PdfReader(stream)
    except Exception as exc:
        raise DocumentLoadError("The file is not a readable PDF.") from exc

    pages = []
    full_text_parts = []

    for page_idx, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        cleaned = extracted.strip()
        pages.append({"page_number": page_idx, "text": cleaned})
        if cleaned:
            full_text_parts.append(cleaned)

    full_text = "\n\n".join(full_text_parts)
    stem = Path(filename).stem
    first_line = full_text.splitlines()[0].strip() if full_text else stem
    resolved_doc_type = doc_type or _detect_doc_type(full_text, filename)

    return {
        "doc_id": stem,
        "source": filename,
        "file_name": filename,
        "title": first_line,
        "doc_type": resolved_doc_type,
        "project_id": project_id,
        "scope": scope,
        "pages": pages,
        "page_count": len(pages),
        "text": full_text,
    }


def load_document(
    path_or_file: Union[str, Path, BinaryIO, bytes],
    filename: Optional[str] = None,
    project_id: str = "global",
    scope: str = "global",
    doc_type: Optional[str] = None,
) -> dict:
    """Load a single document (.pdf or .txt) from disk or stream into a document dict."""
    if isinstance(path_or_file, (str, Path)):
        path = Path(path_or_file)
        name = filename or path.name
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return load_pdf(path, filename=name, project_id=project_id, scope=scope, doc_type=doc_type)

        text = path.read_text(encoding="utf-8").strip()
        stem = path.stem
    elif isinstance(path_or_file, bytes):
        name = filename or "document.txt"
        if name.lower().endswith(".pdf") or path_or_file.startswith(b"%PDF"):
            return load_pdf(path_or_file, filename=name, project_id=project_id, scope=scope, doc_type=doc_type)
        text = path_or_file.decode("utf-8", errors="replace").strip()
        stem = Path(name).stem
    else:
        # File-like object
        name = filename or getattr(path_or_file, "name", "document.txt")
        if name.lower().endswith(".pdf"):
            return load_pdf(path_or_file, filename=name, project_id=project_id, scope=scope, doc_type=doc_type)
        raw_bytes = path_or_file.read()
        if isinstance(raw_bytes, str):
            text = raw_bytes.strip()
        else:
            text = raw_bytes.decode("utf-8", errors="replace").strip()
        stem = Path(name).stem

    first_line = text.splitlines()[0].strip() if text else stem
    resolved_doc_type = doc_type or _detect_doc_type(text, name)

    return {
        "doc_id": stem,
        "source": name,
        "file_name": name,
        "title": first_line,
        "doc_type": resolved_doc_type,
        "project_id": project_id,
        "scope": scope,
        "pages": [{"page_number": 1, "text": text}],
        "page_count": 1,
        "text": text,
    }


def load_documents(
    docs_dir: Union[str, Path] = DOCS_DIR,
    project_id: str = "global",
    scope: str = "global",
) -> list[dict]:
    """Load all supported documents (.txt and .pdf) in docs_dir."""
    docs_dir = Path(docs_dir)
    if not docs_dir.is_dir():
        raise FileNotFoundError(f"Documents folder not found: {docs_dir}")

    documents = []
    # Collect files sorted by name
    all_files = sorted(
        [p for p in docs_dir.iterdir() if p.is_file() and p.suffix.lower() in [".txt", ".pdf"]]
    )
    for path in all_files:
        doc = load_document(path, project_id=project_id, scope=scope)
        if doc["text"]:  # skip empty files
            documents.append(doc)
    return documents


if __name__ == "__main__":
    docs = load_documents()
    print(f"Loaded {len(docs)} documents from {DOCS_DIR}\n")
    for d in docs:
        print(
            f"- {d['source']:<38} {d['doc_type']:<18} "
            f"{d['page_count']} page(s) {len(d['text'].split()):>4} words"
        )
