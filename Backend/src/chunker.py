"""Split documents into retrievable chunks with page and project provenance.

Every created chunk retains metadata:
    {
        "id":          "building_code_structural__chunk_003",
        "doc_id":      "building_code_structural",
        "text":        "<document title>\\nSection 4.2 Rebar Spacing\\n<body>",
        "quote":       "<body only, used for citations>",
        "source":      "building_code_structural.pdf",
        "file_name":   "building_code_structural.pdf",
        "page_number": 3,
        "page_end":    3,
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

# Matches the start of a clause: "Section 4.2 Title", "Clause CW-3 Title", "Finding A-1 Title".
# The id cannot end in a trailing dot, so "Section 4.2 of the code" is not split
# into a fake heading when a sentence merely mentions a clause.
HEADING_RE = re.compile(
    r"^(Section|Clause|Finding|Article|Part|Chapter)\s+([A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*)\s*(.*?)$",
    re.IGNORECASE,
)
NUMBERED_HEADING_RE = re.compile(r"^(\d{1,4}(?:\.\d+)+)\s+(\S.*?)\s*$")
CODED_HEADING_RE = re.compile(r"^([A-Z]{1,6}-\d+[A-Za-z0-9]*)\s+(\S.*?)\s*$")

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


def _match_heading(line: str):
    """Return (kind, section_id, title) for known heading styles, else None.

    The labeled form (Section / Clause / Finding) is tried first so the sample
    documents keep their existing section ids. Numbered and coded headings
    cover documents that omit the label word.
    """
    stripped = line.strip()
    match = HEADING_RE.match(stripped)
    if match:
        kind, section_id, title = match.groups()
        title = (title or "").strip()
        # A real heading title is empty or starts with a capital letter.
        # Lowercase continuations ("Section 4.2 of the code") stay in the body.
        if title and (not title[0].isalpha() or title[0].islower() or "status:" in title.lower()):
            return None
        return kind, section_id, title
    numbered = NUMBERED_HEADING_RE.match(stripped)
    if numbered:
        return "Section", numbered.group(1), numbered.group(2).strip()
    coded = CODED_HEADING_RE.match(stripped)
    if coded:
        return "Clause", coded.group(1), coded.group(2).strip()
    return None


def _split_into_sections(text: str) -> list[dict]:
    """Return [{'section', 'section_id', 'body'}] for each heading found."""
    sections = []
    current = None
    for line in text.splitlines():
        match = _match_heading(line)
        if match:
            if current:
                sections.append(current)
            kind, section_id, title = match
            label = f"{kind} {section_id} {title}".strip()
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


def _sections_on_page(page_text: str) -> tuple[str, list[dict]]:
    """Split one page. Text before the first heading is returned separately.

    That leading text continues the previous page's section when a clause
    crosses a page boundary. It is not discarded.
    """
    leading: list[str] = []
    current = None
    sections = []
    for line in page_text.splitlines():
        match = _match_heading(line)
        if match:
            if current:
                sections.append(current)
            kind, section_id, title = match
            current = {
                "section": f"{kind} {section_id} {title}".strip(),
                "section_id": section_id,
                "lines": [],
            }
        elif current is not None:
            if line.strip():
                current["lines"].append(line.strip())
        elif line.strip():
            leading.append(line.strip())
    if current:
        sections.append(current)
    bodies = [
        {"section": s["section"], "section_id": s["section_id"], "body": " ".join(s["lines"])}
        for s in sections
    ]
    return " ".join(leading), bodies


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
    page_count = int(doc.get("page_count") or 0)

    chunks = []

    def append_piece(section: dict, piece: str, page_num: int) -> None:
        chunks.append({
            "id": f"{stem}__chunk_{len(chunks):03d}",
            "doc_id": stem,
            "text": f"{title}\n{section['section']}\n{piece}",
            "quote": piece,
            "source": filename,
            "file_name": filename,
            "title": title,
            "page_number": page_num,
            "page_end": page_num,
            "page_count": page_count or page_num,
            "section": section["section"],
            "section_id": section["section_id"],
            "project_id": resolved_project_id,
            "scope": resolved_scope,
            "doc_type": resolved_doc_type,
        })

    # If the document contains structured page data (e.g. from PDF loader)
    if "pages" in doc and doc["pages"]:
        last_section = None
        for page_info in doc["pages"]:
            page_num = int(page_info.get("page_number", 1))
            page_text = page_info.get("text", "").strip()
            if not page_text:
                continue

            leading, sections = _sections_on_page(page_text)
            if leading:
                if last_section:
                    target = last_section
                else:
                    target = {
                        "section": f"{title} (Page {page_num})",
                        "section_id": f"P{page_num}",
                    }
                for piece in _split_long_text(leading, size, overlap):
                    append_piece(target, piece, page_num)

            if not sections and not leading:
                fallback_section = last_section or {
                    "section": f"{title} (Page {page_num})",
                    "section_id": f"P{page_num}",
                }
                for piece in _split_long_text(page_text, size, overlap):
                    append_piece(fallback_section, piece, page_num)
                continue

            for sec in sections:
                last_section = {"section": sec["section"], "section_id": sec["section_id"]}
                body = sec["body"] or sec["section"]
                for piece in _split_long_text(body, size, overlap):
                    append_piece(sec, piece, page_num)
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
                append_piece(sec, piece, page_num)

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
