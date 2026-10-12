"""FastAPI service for BuildSure."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import re
import uuid
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config import (
    CORS_ORIGINS,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    GROQ_API_KEY,
    MAX_UPLOAD_BYTES,
    SIMILARITY_THRESHOLD,
)
from src.db import (
    get_documents_collection,
    get_projects_collection,
    init_db,
    ping_db,
    storage_kind,
)
from src.deficiencies import analyze_deficiencies, classify_chunk
from src.embedder import embed_texts
from src.ingestion import UploadRejected, assert_can_read, delete_document, ingest_pdf_bytes, project_exists, stored_pdf_path
from src.metadata import resolve_filter_doc_type
from src.rag import NO_EVIDENCE, generate_compliance_answer
from src.retriever import IndexNotBuiltError, retrieve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("buildsure-api")

_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_GENERATION_NOTES = {
    "extractive": (
        "GROQ_API_KEY is not configured. The summary quotes retrieved text and is not a "
        "model-written compliance determination."
    ),
    "extractive_after_citation_check": (
        "The model response was discarded because its citations did not match retrieved sources. "
        "The summary quotes those sources instead."
    ),
    "extractive_after_llm_error": (
        "The language model request failed. The summary quotes retrieved text instead."
    ),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the document store when the process starts."""
    logger.info("Starting BuildSure API")
    try:
        init_db()
    except Exception as exc:
        logger.warning("Database initialization warning: %s", type(exc).__name__)
    yield
    logger.info("Shutting down BuildSure API")


app = FastAPI(
    title="BuildSure Compliance API",
    description="Project-aware compliance search over uploaded building documents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    project_name: Optional[str] = None
    name: Optional[str] = None
    location: Optional[str] = ""
    is_global: bool = Field(False, alias="isGlobal")

    @model_validator(mode="after")
    def require_name(self):
        chosen = (self.project_name or self.name or "").strip()
        if not chosen:
            raise ValueError("project_name is required")
        if len(chosen) > 200:
            raise ValueError("project_name is too long")
        self.project_name = chosen
        self.name = chosen
        self.location = (self.location or "").strip()
        if len(self.location) > 300:
            raise ValueError("location is too long")
        if self.id is not None:
            if not _PROJECT_ID_RE.match(self.id):
                raise ValueError("project id contains unsupported characters")
            if self.id == "global":
                raise ValueError("project id 'global' is reserved")
        return self


class ProjectResponse(BaseModel):
    id: str
    name: str
    location: str
    isGlobal: bool = False
    created_at: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language compliance question")
    project_id: str = Field("global", description="Active project workspace ID")
    doc_type: Optional[str] = None
    doc_type_filter: Optional[str] = Field(
        None,
        description="All, building_code, specification, or inspection_report",
    )


class SourceCard(BaseModel):
    id: str
    doc_name: str
    documentName: str
    document_name: str
    documentId: str
    document_id: str
    section: str
    section_id: str
    page: int
    page_number: int
    quote: str
    snippet: str
    text: str
    scope: str
    doc_type: str
    category: str
    score: float
    pdf_url: str
    page_count: Optional[int] = None
    is_deficiency: bool = False
    finding_status: str = "none"


class Citation(BaseModel):
    label: str
    scope: str
    documentName: str


class SearchResponse(BaseModel):
    ai_summary: str
    has_deficiency: bool
    deficiency_text: Optional[str] = None
    deficiency_status: Optional[str] = None
    source_cards: list[SourceCard]
    citations: list[Citation] = []
    generation_mode: str
    retrieval_note: Optional[str] = None


def _map_frontend_category(doc_type: str) -> str:
    normalized = (doc_type or "").lower()
    if "spec" in normalized:
        return "project-spec"
    if "inspection" in normalized:
        return "inspection-report"
    return "building-code"


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _document_out(document: dict) -> dict:
    scope = document.get("scope")
    doc_type = document.get("doc_type") or ""
    size_bytes = int(document.get("size_bytes") or 0)
    return {
        "id": document.get("doc_id"),
        "doc_id": document.get("doc_id"),
        "name": document.get("file_name"),
        "file_name": document.get("file_name"),
        "scope": "global" if scope == "global" else "local",
        "storage_scope": scope,
        "category": _map_frontend_category(doc_type),
        "doc_type": doc_type,
        "projectId": document.get("project_id"),
        "project_id": document.get("project_id"),
        "pages": document.get("page_count") or 0,
        "size": _format_size(size_bytes),
        "size_bytes": size_bytes,
        "uploadedAt": (document.get("uploaded_at") or "")[:10],
        "uploaded_at": document.get("uploaded_at"),
        "processing_status": document.get("processing_status"),
        "status_detail": document.get("status_detail") or "",
    }


def _pdf_url(doc_id: str, page: int, scope: str, project_id: str) -> str:
    page_number = page if page > 0 else 1
    if scope == "project":
        return (
            f"/api/documents/{doc_id}/file?project_id={quote(project_id, safe='')}"
            f"&page={page_number}#page={page_number}"
        )
    return f"/api/documents/{doc_id}/file?page={page_number}#page={page_number}"


def _source_card(chunk: dict) -> SourceCard:
    doc_name = chunk.get("file_name") or chunk.get("source") or "Document"
    doc_id = chunk.get("doc_id") or ""
    storage_scope = chunk.get("scope") or "global"
    ui_scope = "local" if storage_scope == "project" else "global"
    doc_type = chunk.get("doc_type") or "building_code"
    quote = (chunk.get("quote") or chunk.get("text") or "").strip()
    page = int(chunk.get("page_number") or 1)
    finding_status = classify_chunk(chunk)
    page_count = chunk.get("page_count")
    return SourceCard(
        id=str(chunk.get("id") or uuid.uuid4()),
        doc_name=doc_name,
        documentName=doc_name,
        document_name=doc_name,
        documentId=doc_id,
        document_id=doc_id,
        section=chunk.get("section") or "General",
        section_id=chunk.get("section_id") or "",
        page=page,
        page_number=page,
        quote=quote,
        snippet=quote,
        text=chunk.get("text") or quote,
        scope=ui_scope,
        doc_type=doc_type,
        category=_map_frontend_category(doc_type),
        score=float(chunk.get("score") or 0.0),
        pdf_url=_pdf_url(doc_id, page, storage_scope, chunk.get("project_id") or ""),
        page_count=int(page_count) if page_count else None,
        is_deficiency=finding_status == "open",
        finding_status=finding_status,
    )


def _above_threshold(chunks: list[dict]) -> list[dict]:
    return [chunk for chunk in chunks if float(chunk.get("score") or 0.0) >= SIMILARITY_THRESHOLD]


def _collect_chunks(query: str, project_id: str, doc_filter: Optional[str]) -> list[dict]:
    try:
        primary = retrieve(query, active_project_id=project_id, doc_type_filter=doc_filter)
    except IndexNotBuiltError:
        return []
    kept = _above_threshold(primary)
    if doc_filter is not None:
        return kept
    try:
        inspection = retrieve(
            query,
            active_project_id=project_id,
            doc_type_filter="inspection_report",
        )
    except IndexNotBuiltError:
        inspection = []
    merged = []
    seen = set()
    for chunk in kept + _above_threshold(inspection):
        key = chunk.get("id") or (
            chunk.get("doc_id"),
            chunk.get("page_number"),
            chunk.get("section_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(chunk)
    return merged


def _empty_search() -> SearchResponse:
    return SearchResponse(
        ai_summary=NO_EVIDENCE,
        has_deficiency=False,
        deficiency_text=None,
        deficiency_status=None,
        source_cards=[],
        citations=[],
        generation_mode="no_evidence",
        retrieval_note=None,
    )


def _raise_upload(exc: UploadRejected) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.get("/api/health", tags=["Health"])
def health_check():
    """Report store and provider configuration without revealing secrets."""
    connected = ping_db()
    kind = storage_kind()
    return {
        "status": "healthy" if connected else "degraded",
        "database_connected": connected,
        "storage": kind,
        "vector_search": "atlas_with_cosine_fallback" if kind == "mongo" else "cosine_fallback",
        "llm_configured": bool(GROQ_API_KEY),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EMBEDDING_DIM,
        "service": "BuildSure API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/projects", response_model=ProjectResponse, tags=["Projects"])
def create_project(payload: ProjectRequest):
    """Create a project workspace. An existing id is returned unchanged."""
    projects = get_projects_collection()
    if payload.id:
        existing = projects.find_one({"id": payload.id})
        if existing:
            return ProjectResponse(
                id=existing.get("id"),
                name=existing.get("name"),
                location=existing.get("location", ""),
                isGlobal=bool(existing.get("is_global", False)),
                created_at=existing.get("created_at"),
            )

    project_id = payload.id or f"proj-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    projects.insert_one(
        {
            "id": project_id,
            "name": payload.name,
            "location": payload.location or "",
            "is_global": bool(payload.is_global),
            "created_at": created_at,
        }
    )
    return ProjectResponse(
        id=project_id,
        name=payload.name or "",
        location=payload.location or "",
        isGlobal=bool(payload.is_global),
        created_at=created_at,
    )


@app.get("/api/projects", tags=["Projects"])
def list_projects():
    """List persisted project workspaces. The global scope is not a project row."""
    projects = []
    for project in get_projects_collection().find({}, {"_id": 0}):
        projects.append(
            {
                "id": project.get("id"),
                "name": project.get("name"),
                "location": project.get("location", ""),
                "isGlobal": bool(project.get("is_global", False)),
                "created_at": project.get("created_at"),
            }
        )
    return projects


@app.post("/api/documents/upload", tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),
    project_id: str = Form("global"),
    scope: str = Form("project"),
    doc_type: str = Form("building_code"),
):
    """Upload a PDF into the global repository or one project."""
    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        return ingest_pdf_bytes(
            file_bytes=file_bytes,
            filename=file.filename or "",
            project_id=project_id,
            scope=scope,
            doc_type=doc_type,
            embed_fn=embed_texts,
        )
    except UploadRejected as exc:
        _raise_upload(exc)


@app.get("/api/documents", tags=["Documents"])
def list_documents(project_id: str = Query("global")):
    """List global documents plus documents owned by the requested project."""
    visible = []
    for document in get_documents_collection().find({}):
        if document.get("scope") == "global" or document.get("project_id") == project_id:
            visible.append(_document_out(document))
    visible.sort(key=lambda item: item.get("uploaded_at") or "", reverse=True)
    return visible


@app.get("/api/documents/{doc_id}/file", tags=["Documents"])
def read_document_file(doc_id: str, project_id: Optional[str] = Query(None)):
    """Serve an uploaded PDF. Project files require the owning project id."""
    try:
        path = stored_pdf_path(doc_id)
        document = get_documents_collection().find_one({"doc_id": doc_id})
        if not document:
            raise UploadRejected(404, "Document not found")
        assert_can_read(document, project_id)
    except UploadRejected as exc:
        _raise_upload(exc)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")
    filename = re.sub(r'[\r\n"]', "", document.get("file_name") or "document.pdf")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
    )


@app.delete("/api/documents/{doc_id}", tags=["Documents"])
def remove_document(doc_id: str, project_id: Optional[str] = Query(None)):
    """Delete a document, its chunks, and the stored PDF."""
    try:
        delete_document(doc_id, project_id)
    except UploadRejected as exc:
        _raise_upload(exc)
    return {"status": "deleted", "doc_id": doc_id}


@app.post("/api/search", response_model=SearchResponse, tags=["Search"])
def search_compliance(payload: SearchRequest):
    """Search global regulations and the active project's documents."""
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Search query cannot be empty")

    project_id = (payload.project_id or "global").strip() or "global"
    if project_id != "global" and not project_exists(project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    raw_filter = payload.doc_type_filter if payload.doc_type_filter is not None else payload.doc_type
    try:
        doc_filter = resolve_filter_doc_type(raw_filter)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        chunks = _collect_chunks(query, project_id, doc_filter)
    except Exception:
        logger.exception("Retrieval failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Search is temporarily unavailable")

    if not chunks:
        return _empty_search()

    generated = generate_compliance_answer(query=query, retrieved_chunks=chunks)
    if generated.get("generation_mode") == "no_evidence" or generated.get("answer") == NO_EVIDENCE:
        return _empty_search()

    report = analyze_deficiencies(chunks)
    citations = [
        Citation(label=item["label"], scope=item["scope"], documentName=item["documentName"])
        for item in generated.get("citations", [])
    ]
    return SearchResponse(
        ai_summary=generated.get("answer") or NO_EVIDENCE,
        has_deficiency=report.has_deficiency,
        deficiency_text=report.text,
        deficiency_status=report.status,
        source_cards=[_source_card(chunk) for chunk in chunks],
        citations=citations,
        generation_mode=generated.get("generation_mode") or "extractive",
        retrieval_note=_GENERATION_NOTES.get(generated.get("generation_mode") or ""),
    )
