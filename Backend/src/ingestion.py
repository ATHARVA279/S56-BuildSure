"""Validate, parse, embed, and store an uploaded PDF.

A document record is written before indexing and is marked `indexed` only after
chunks and the original file are stored. Failures stay `failed` or
`no_extractable_text` and do not leave searchable chunks behind.
"""
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.chunker import chunk_document
from src.config import EMBEDDING_DIM, MAX_UPLOAD_BYTES, UPLOAD_DIR
from src.db import get_chunks_collection, get_documents_collection, get_projects_collection
from src.embedder import embed_texts
from src.loader import DocumentLoadError, load_pdf
from src.metadata import normalize_scope, normalize_upload_doc_type

DOC_ID_RE = re.compile(r"^doc_[a-f0-9]{8}$")


class UploadRejected(Exception):
    """A user-facing upload or file-access rejection with an HTTP status."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def project_exists(project_id: str) -> bool:
    if not project_id:
        return False
    return get_projects_collection().find_one({"id": project_id}) is not None


def ingest_pdf_bytes(
    *,
    file_bytes: bytes,
    filename: str,
    project_id: str,
    scope: str,
    doc_type: str,
    embed_fn=None,
) -> dict:
    """Parse one PDF and store its metadata, chunks, and original bytes."""
    embed = embed_fn or embed_texts
    safe_name = Path(filename or "").name
    if not safe_name:
        raise UploadRejected(400, "Filename cannot be empty")
    if not file_bytes:
        raise UploadRejected(400, "Uploaded file is empty")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise UploadRejected(413, "Uploaded file exceeds the size limit")
    if not safe_name.lower().endswith(".pdf") or not file_bytes.startswith(b"%PDF"):
        raise UploadRejected(400, "Only PDF files can be uploaded")

    try:
        clean_scope = normalize_scope(scope)
        canonical_type = normalize_upload_doc_type(doc_type)
    except ValueError as exc:
        raise UploadRejected(400, str(exc)) from exc

    if clean_scope == "global":
        stored_project_id = "global"
    else:
        if not project_id or project_id == "global":
            raise UploadRejected(400, "A project document requires a valid project_id")
        if not project_exists(project_id):
            raise UploadRejected(404, "Project not found")
        stored_project_id = project_id

    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    uploaded_at = datetime.now(timezone.utc).isoformat()
    docs_col = get_documents_collection()
    chunks_col = get_chunks_collection()
    docs_col.insert_one(
        {
            "doc_id": doc_id,
            "project_id": stored_project_id,
            "file_name": safe_name,
            "scope": clean_scope,
            "doc_type": canonical_type,
            "title": safe_name,
            "page_count": 0,
            "size_bytes": len(file_bytes),
            "uploaded_at": uploaded_at,
            "processing_status": "processing",
            "status_detail": "",
            "chunk_count": 0,
        }
    )

    try:
        parsed = load_pdf(
            file_bytes,
            filename=safe_name,
            project_id=stored_project_id,
            scope=clean_scope,
            doc_type=canonical_type,
        )
    except DocumentLoadError as exc:
        _mark(docs_col, doc_id, "failed", str(exc))
        raise UploadRejected(400, str(exc)) from exc

    parsed["doc_id"] = doc_id
    parsed["project_id"] = stored_project_id
    parsed["scope"] = clean_scope
    parsed["doc_type"] = canonical_type
    page_count = int(parsed.get("page_count") or 0)
    _mark(
        docs_col,
        doc_id,
        "processing",
        "",
        extra={"page_count": page_count, "title": parsed.get("title") or safe_name},
    )

    if page_count == 0 or not (parsed.get("text") or "").strip():
        detail = (
            "This PDF has no extractable text. It may be a scanned document. "
            "OCR is not implemented."
        )
        _mark(docs_col, doc_id, "no_extractable_text", detail, extra={"page_count": page_count})
        raise UploadRejected(422, detail)

    chunks = chunk_document(
        parsed,
        project_id=stored_project_id,
        scope=clean_scope,
        doc_type=canonical_type,
    )
    if not chunks:
        detail = (
            "This PDF has no extractable text. It may be a scanned document. "
            "OCR is not implemented."
        )
        _mark(docs_col, doc_id, "no_extractable_text", detail)
        raise UploadRejected(422, detail)

    try:
        embeddings = embed([chunk["text"] for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise RuntimeError("Embedding count does not match chunk count")
        for embedding in embeddings:
            if len(embedding) != EMBEDDING_DIM:
                raise RuntimeError(
                    f"Embedding dimension {len(embedding)} does not match configured dimension {EMBEDDING_DIM}"
                )
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = [float(value) for value in embedding]
            chunk["doc_id"] = doc_id
        _save_pdf(doc_id, file_bytes)
        chunks_col.insert_many(chunks)
    except UploadRejected:
        chunks_col.delete_many({"doc_id": doc_id})
        _delete_pdf(doc_id)
        raise
    except Exception as exc:
        chunks_col.delete_many({"doc_id": doc_id})
        _delete_pdf(doc_id)
        _mark(docs_col, doc_id, "failed", "Indexing failed")
        raise UploadRejected(500, "Document indexing failed") from exc

    _mark(
        docs_col,
        doc_id,
        "indexed",
        "",
        extra={"chunk_count": len(chunks), "page_count": page_count},
    )
    return {
        "status": "success",
        "doc_id": doc_id,
        "file_name": safe_name,
        "project_id": stored_project_id,
        "scope": clean_scope,
        "doc_type": canonical_type,
        "pages_processed": page_count,
        "chunks_stored": len(chunks),
        "uploaded_at": uploaded_at,
        "processing_status": "indexed",
    }


def stored_pdf_path(doc_id: str) -> Path:
    """Resolve the on-disk PDF for a document id. Rejects path tricks."""
    if not DOC_ID_RE.match(doc_id or ""):
        raise UploadRejected(404, "Document not found")
    root = UPLOAD_DIR.resolve()
    path = (root / f"{doc_id}.pdf").resolve()
    if path.parent != root:
        raise UploadRejected(404, "Document not found")
    return path


def assert_can_read(document: dict, project_id: str | None) -> None:
    """Global files are readable. Project files require the owning project id."""
    if document.get("scope") == "global":
        return
    if project_id and project_id == document.get("project_id"):
        return
    raise UploadRejected(404, "Document not found")


def delete_document(doc_id: str, project_id: str | None) -> None:
    docs_col = get_documents_collection()
    document = docs_col.find_one({"doc_id": doc_id})
    if not document:
        raise UploadRejected(404, "Document not found")
    if document.get("scope") != "global":
        assert_can_read(document, project_id)
    get_chunks_collection().delete_many({"doc_id": doc_id})
    _delete_pdf(doc_id)
    docs_col.delete_many({"doc_id": doc_id})


def _mark(collection, doc_id: str, status: str, detail: str, extra: dict | None = None) -> None:
    fields = {"processing_status": status, "status_detail": detail}
    if extra:
        fields.update(extra)
    collection.update_one({"doc_id": doc_id}, {"$set": fields})


def _save_pdf(doc_id: str, file_bytes: bytes) -> None:
    path = stored_pdf_path(doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file_bytes)


def _delete_pdf(doc_id: str) -> None:
    if not DOC_ID_RE.match(doc_id or ""):
        return
    path = stored_pdf_path(doc_id)
    if path.exists():
        path.unlink()
