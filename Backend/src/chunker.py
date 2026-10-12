"""Split documents into retrievable chunks with page and project provenance.

Every created chunk retains metadata:
    {
        "id":          "building_code_structural__chunk_003",
        "doc_id":      "building_code_structural",
        "text":        "<document title>\\nSection 4.2 Rebar Spacing\\n<body>",
        "source":      "building_code_structural.pdf",
        "file_name":   "building_code_structural.pdf",
        "page_number": 3,
        "section":     "Section 4.2 Rebar Spacing",
        "section_id":  "4.2",
        "project_id":  "global" | "alpha",
        "scope":       "global" | "project",
        "doc_type":    "building_code" | "spec" | "inspection_report",
    }
"""
import re
from pathlib import Path
from typing import Optional

from src.config import CHUNK_OVERLAP, CHUNK_SIZE

# Matches the start of a clause: "Section 4.2 Title", "Clause CW-3 Title", "Finding A-1 Title"
HEADING_RE = re.compile(
    r"^(Section|Clause|Finding|Article|Part|Chapter)\s+([A-Za-z0-9.\-]+)\s*(.*?)$",
    re.IGNORECASE,
)

# Standardize doc types
_VALID_DOC_TYPES = {"building_code", "spec", "inspection_report"}
_TYPE_NORMALIZER = {
    "building code": "building_code",
    "building_code": "building_code",
    "project specification": "spec",
    "specification": "spec",
    "spec": "spec",
    "inspection report": "inspection_report",
    "inspection": "inspection_report",
    "inspection_report": "inspection_report",
}


def _normalize_doc_type(raw_type: Optional[str]) -> str:
    """Normalize raw document type to building_code, spec, or inspection_report."""
    if not raw_type:
        return "building_code"
    lowered = raw_type.strip().lower()
    if lowered in _VALID_DOC_TYPES:
        return lowered
    return _TYPE_NORMALIZER.get(lowered, "building_code")


def _split_into_sections(text: str) -> list[dict]:
    """Return [{'section', 'section_id', 'body'}] for each heading found."""
    sections = []
    current = None
    for line in text.splitlines():
        match = HEADING_RE.match(line.strip())
        if match:
            if current:
                sections.append(current)
            kind, section_id, title = match.groups()
            title_clean = title.strip()
            label = f"{kind} {section_id} {title_clean}".strip()
            current = {
                "section": label,
                "section_id": section_id,
                "lines": [],
            }
        elif current is not None and line.strip():
            current["lines"].append(line.strip())
    if current:
        sections.append(current)
    return [
        {"section": s["section"], "section_id": s["section_id"], "body": " ".join(s["lines"])}
        for s in sections
    ]


def _split_long_text(body: str, size: int, overlap: int) -> list[str]:
    """Split an over-long body into word windows of `size` with `overlap`."""
    words = body.split()
    if len(words) <= size:
        return [body]
    step = max(size - overlap, 1)
    pieces = []
    for start in range(0, len(words), step):
        pieces.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
    return pieces


def chunk_document(
    doc: dict,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    project_id: Optional[str] = None,
    scope: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> list[dict]:
    """Turn one loaded document into a list of chunks with page provenance."""
    filename = doc.get("file_name") or doc.get("source") or "document"
    stem = doc.get("doc_id") or Path(filename).stem
    title = doc.get("title") or stem

    resolved_project_id = project_id or doc.get("project_id", "global")
    resolved_scope = scope or doc.get("scope", "global")
    resolved_doc_type = _normalize_doc_type(doc_type or doc.get("doc_type"))

    chunks = []

    # If the document contains structured page data (e.g. from PDF loader)
    if "pages" in doc and doc["pages"]:
        last_section = None
        for page_info in doc["pages"]:
            page_num = int(page_info.get("page_number", 1))
            page_text = page_info.get("text", "").strip()
            if not page_text:
                continue

            sections = _split_into_sections(page_text)
            if not sections:
                # No heading on this page: use previous section or page label
                fallback_section = last_section or {
                    "section": f"{title} (Page {page_num})",
                    "section_id": f"P{page_num}",
                }
                for piece in _split_long_text(page_text, size, overlap):
                    chunks.append({
                        "id": f"{stem}__chunk_{len(chunks):03d}",
                        "doc_id": stem,
                        "text": f"{title}\n{fallback_section['section']}\n{piece}",
                        "source": filename,
                        "file_name": filename,
                        "title": title,
                        "page_number": page_num,
                        "section": fallback_section["section"],
                        "section_id": fallback_section["section_id"],
                        "project_id": resolved_project_id,
                        "scope": resolved_scope,
                        "doc_type": resolved_doc_type,
                    })
            else:
                for sec in sections:
                    last_section = sec
                    body = sec["body"] or sec["section"]
                    for piece in _split_long_text(body, size, overlap):
                        chunks.append({
                            "id": f"{stem}__chunk_{len(chunks):03d}",
                            "doc_id": stem,
                            "text": f"{title}\n{sec['section']}\n{piece}",
                            "source": filename,
                            "file_name": filename,
                            "title": title,
                            "page_number": page_num,
                            "section": sec["section"],
                            "section_id": sec["section_id"],
                            "project_id": resolved_project_id,
                            "scope": resolved_scope,
                            "doc_type": resolved_doc_type,
                        })
    else:
        # Fallback for plain text document without explicit pages
        page_num = int(doc.get("page_number", 1))
        full_text = doc.get("text", "")
        sections = _split_into_sections(full_text)
        if not sections:
            sections = [{"section": title, "section_id": "", "body": " ".join(full_text.split())}]

        for sec in sections:
            body = sec["body"] or sec["section"]
            for piece in _split_long_text(body, size, overlap):
                chunks.append({
                    "id": f"{stem}__chunk_{len(chunks):03d}",
                    "doc_id": stem,
                    "text": f"{title}\n{sec['section']}\n{piece}",
                    "source": filename,
                    "file_name": filename,
                    "title": title,
                    "page_number": page_num,
                    "section": sec["section"],
                    "section_id": sec["section_id"],
                    "project_id": resolved_project_id,
                    "scope": resolved_scope,
                    "doc_type": resolved_doc_type,
                })

    return chunks


def chunk_documents(
    docs: list[dict],
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    project_id: Optional[str] = None,
    scope: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> list[dict]:
    """Chunk a list of documents."""
    chunks = []
    for doc in docs:
        chunks.extend(
            chunk_document(
                doc,
                size=size,
                overlap=overlap,
                project_id=project_id,
                scope=scope,
                doc_type=doc_type,
            )
        )
    return chunks


if __name__ == "__main__":
    from src.loader import load_documents

    all_chunks = chunk_documents(load_documents())
    print(f"{len(all_chunks)} chunks created\n")
    for c in all_chunks[:6]:
        print(f"{c['id']:<35} p.{c['page_number']} [{c['scope']}/{c['doc_type']}] {c['section']}")
    print("...")
