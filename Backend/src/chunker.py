"""Split documents into retrievable chunks.

Strategy: split on clause headings ("Section 4.2 ...", "Clause CW-3 ...",
"Finding B-1 ...") so each chunk is one complete clause with its own citation
label. A clause longer than CHUNK_SIZE words is split further with overlap.

Each chunk is a dict:
    {
        "id":          "building_code_structural__chunk_003",
        "text":        "<document title>\\nSection 4.2 Rebar Spacing in Slabs\\n<body>",
        "source":      "building_code_structural.txt",
        "doc_type":    "building_code",
        "section":     "Section 4.2 Rebar Spacing in Slabs",
        "section_id":  "4.2",
    }
"""
import re
from pathlib import Path

from src.config import CHUNK_OVERLAP, CHUNK_SIZE

# Matches the start of a clause: "Section 4.2 Title", "Clause CW-3 Title", "Finding A-1 Title"
HEADING_RE = re.compile(r"^(Section|Clause|Finding)\s+([A-Za-z0-9.\-]+)\s+(.+)$")


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
            current = {
                "section": f"{kind} {section_id} {title}",
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
        pieces.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return pieces


def chunk_document(doc: dict, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Turn one loaded document into a list of chunks."""
    stem = Path(doc["source"]).stem
    sections = _split_into_sections(doc["text"])

    # No recognisable headings: fall back to plain word windows over the whole text.
    if not sections:
        sections = [{"section": doc["title"], "section_id": "", "body": " ".join(doc["text"].split())}]

    chunks = []
    for sec in sections:
        for piece in _split_long_text(sec["body"], size, overlap):
            chunks.append({
                "id": f"{stem}__chunk_{len(chunks):03d}",
                "text": f"{doc['title']}\n{sec['section']}\n{piece}",
                "source": doc["source"],
                "doc_type": doc["doc_type"],
                "section": sec["section"],
                "section_id": sec["section_id"],
            })
    return chunks


def chunk_documents(docs: list[dict], size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Chunk a list of documents."""
    chunks = []
    for doc in docs:
        chunks.extend(chunk_document(doc, size, overlap))
    return chunks


if __name__ == "__main__":
    from src.loader import load_documents

    all_chunks = chunk_documents(load_documents())
    print(f"{len(all_chunks)} chunks created\n")
    for c in all_chunks[:6]:
        print(f"{c['id']:<42} {c['section']}")
    print("...")
