"""Shared document scope and type normalization.

Canonical stored document types stay `building_code`, `spec`, and
`inspection_report` so existing chunks and tests keep their labels.
Upload and search accept the public aliases `specification` and the
frontend filter names (`building-codes`, `project-specs`, `inspection-reports`).
"""
from typing import Optional

_DOC_TYPE_ALIASES = {
    "building-code": "building_code",
    "building-codes": "building_code",
    "building code": "building_code",
    "building_code": "building_code",
    "project-spec": "spec",
    "project-specs": "spec",
    "specification": "spec",
    "specifications": "spec",
    "project specification": "spec",
    "spec": "spec",
    "inspection-report": "inspection_report",
    "inspection-reports": "inspection_report",
    "inspection report": "inspection_report",
    "inspection": "inspection_report",
    "inspection_report": "inspection_report",
}


def resolve_filter_doc_type(raw: Optional[str]) -> Optional[str]:
    """Return a canonical type, or None when the caller asked for every type."""
    if raw is None:
        return None
    cleaned = raw.strip().lower()
    if cleaned in {"", "all"}:
        return None
    if cleaned not in _DOC_TYPE_ALIASES:
        raise ValueError(
            "doc_type_filter must be All, building_code, specification, or inspection_report"
        )
    return _DOC_TYPE_ALIASES[cleaned]


def normalize_upload_doc_type(raw: Optional[str]) -> str:
    """Validate a document type supplied with an upload."""
    if raw is None or not str(raw).strip():
        raise ValueError("doc_type is required")
    cleaned = str(raw).strip().lower()
    if cleaned not in _DOC_TYPE_ALIASES:
        raise ValueError("doc_type must be building_code, specification, or inspection_report")
    return _DOC_TYPE_ALIASES[cleaned]


def normalize_scope(raw: Optional[str]) -> str:
    """Accept global/project plus the frontend's `local` alias."""
    cleaned = (raw or "").strip().lower()
    if cleaned == "local":
        return "project"
    if cleaned in {"global", "project"}:
        return cleaned
    raise ValueError("scope must be global or project")
