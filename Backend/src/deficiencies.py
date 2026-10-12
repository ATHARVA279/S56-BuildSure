"""Classify inspection-report findings from retrieved text.

Status is taken from the source wording. A closed or resolved finding is not
reported as an active deficiency. A defect-like statement with no status is
flagged for verification instead of being called unresolved.
"""
import re
from dataclasses import dataclass, field

OPEN_RE = re.compile(r"\bstatus\s*:\s*(open|unresolved|outstanding|pending)\b", re.IGNORECASE)
CLOSED_RE = re.compile(r"\bstatus\s*:\s*(closed|resolved|completed|cleared)\b", re.IGNORECASE)
DEFECT_RE = re.compile(
    r"\b(deficiency|does not comply|do not comply|non-?compliant|noncompliance)\b",
    re.IGNORECASE,
)
FINDING_SPLIT_RE = re.compile(r"(?=^Finding\s+[A-Za-z0-9.\-]+)", re.IGNORECASE | re.MULTILINE)


@dataclass
class DeficiencyReport:
    has_deficiency: bool
    status: str | None
    text: str | None
    items: list[dict] = field(default_factory=list)


def classify_text(text: str) -> str:
    """Return open, closed, unverified, or none for one finding body."""
    if not text or not text.strip():
        return "none"
    has_open = OPEN_RE.search(text) is not None
    has_closed = CLOSED_RE.search(text) is not None
    if has_open and not has_closed:
        return "open"
    if has_closed and not has_open:
        return "closed"
    if has_open and has_closed:
        parts = [part for part in FINDING_SPLIT_RE.split(text) if part.strip()]
        if len(parts) > 1:
            statuses = {classify_text(part) for part in parts}
            if "open" in statuses:
                return "open"
            if "unverified" in statuses:
                return "unverified"
            if "closed" in statuses:
                return "closed"
        return "unverified"
    if DEFECT_RE.search(text):
        return "unverified"
    return "none"


def classify_chunk(chunk: dict) -> str:
    """Inspection chunks only. Other document types are never deficiencies."""
    if (chunk.get("doc_type") or "") != "inspection_report":
        return "none"
    text = "\n".join(
        part
        for part in (
            chunk.get("section") or "",
            chunk.get("quote") or "",
            chunk.get("text") or "",
        )
        if part
    )
    return classify_text(text)


def _describe(chunk: dict, status: str) -> str:
    name = chunk.get("file_name") or chunk.get("source") or "inspection report"
    section = chunk.get("section") or "Finding"
    page = int(chunk.get("page_number") or 1)
    quote = (chunk.get("quote") or chunk.get("text") or "").strip()
    label = "Status: open" if status == "open" else "Status: not established in the source"
    return f"{section} ({name}, Page {page}). {label}. {quote}"


def analyze_deficiencies(chunks: list[dict]) -> DeficiencyReport:
    """Build the warning payload from retrieved inspection chunks."""
    open_items = []
    unverified_items = []
    for chunk in chunks:
        status = classify_chunk(chunk)
        if status == "open":
            open_items.append(chunk)
        elif status == "unverified":
            unverified_items.append(chunk)

    if open_items:
        details = " ".join(_describe(chunk, "open") for chunk in open_items)
        return DeficiencyReport(
            has_deficiency=True,
            status="open",
            text=f"DEFICIENCY DETECTED. {details}",
            items=open_items,
        )
    if unverified_items:
        details = " ".join(_describe(chunk, "unverified") for chunk in unverified_items)
        return DeficiencyReport(
            has_deficiency=False,
            status="requires_verification",
            text=(
                "REQUIRES VERIFICATION. A retrieved inspection finding does not establish "
                f"whether it is still unresolved. {details}"
            ),
            items=unverified_items,
        )
    return DeficiencyReport(False, None, None, [])
