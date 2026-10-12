"""Load source documents from disk.

Each document is returned as a dict:
    {
        "source":   "building_code_structural.txt",   # filename, used in citations
        "title":    "BUILDSURE SAMPLE BUILDING CODE - PART 4: ...",
        "doc_type": "building_code" | "specification" | "inspection_report" | "unknown",
        "text":     "<full document text>",
    }
"""
from pathlib import Path

from src.config import DOCS_DIR

# Maps the "Document type:" line in a file to a short, stable label.
_DOC_TYPE_LABELS = {
    "building code": "building_code",
    "project specification": "specification",
    "inspection report": "inspection_report",
}


def _detect_doc_type(text: str, filename: str) -> str:
    """Read the 'Document type:' header; fall back to the filename prefix."""
    for line in text.splitlines()[:10]:
        if line.lower().startswith("document type:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in _DOC_TYPE_LABELS:
                return _DOC_TYPE_LABELS[value]
    name = filename.lower()
    if name.startswith("building_code"):
        return "building_code"
    if name.startswith("spec"):
        return "specification"
    if name.startswith("inspection"):
        return "inspection_report"
    return "unknown"


def load_document(path: Path) -> dict:
    """Load a single .txt file into a document dict."""
    text = Path(path).read_text(encoding="utf-8").strip()
    first_line = text.splitlines()[0].strip() if text else Path(path).stem
    return {
        "source": Path(path).name,
        "title": first_line,
        "doc_type": _detect_doc_type(text, Path(path).name),
        "text": text,
    }


def load_documents(docs_dir: Path = DOCS_DIR) -> list[dict]:
    """Load every .txt file in docs_dir (sorted by name for stable ordering).

    Raises FileNotFoundError if the folder does not exist, so a wrong path
    fails loudly instead of silently producing an empty index.
    """
    docs_dir = Path(docs_dir)
    if not docs_dir.is_dir():
        raise FileNotFoundError(f"Documents folder not found: {docs_dir}")

    documents = []
    for path in sorted(docs_dir.glob("*.txt")):
        doc = load_document(path)
        if doc["text"]:  # skip empty files
            documents.append(doc)
    return documents


if __name__ == "__main__":
    docs = load_documents()
    print(f"Loaded {len(docs)} documents from {DOCS_DIR}\n")
    for d in docs:
        print(f"- {d['source']:<38} {d['doc_type']:<18} {len(d['text'].split()):>4} words")
