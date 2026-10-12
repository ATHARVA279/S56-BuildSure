"""Production-ready FastAPI service for BuildSure / RegFind."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from typing import Any, List, Optional
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.chunker import chunk_document
from src.db import (
    get_chunks_collection,
    get_documents_collection,
    get_projects_collection,
    init_db,
    ping_db,
)
from src.embedder import embed_texts
from src.loader import load_document, load_pdf
from src.rag import generate_compliance_answer
from src.retriever import retrieve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("buildsure-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database initialization."""
    logger.info("Starting BuildSure FastAPI service...")
    try:
        init_db()
        logger.info("Database and vector search index initialization completed.")
    except Exception as exc:
        logger.warning(f"Database initialization warning: {exc}")
    yield
    logger.info("Shutting down BuildSure FastAPI service...")


app = FastAPI(
    title="BuildSure Compliance API",
    description="FastAPI service backed by MongoDB Atlas Vector Search and Groq LLM",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware for seamless frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---
class ProjectRequest(BaseModel):
    id: Optional[str] = Field(None, description="Optional custom project ID")
    name: str = Field(..., description="Project workspace name")
    location: Optional[str] = Field("", description="Project physical location")
    is_global: Optional[bool] = Field(False, alias="isGlobal")


class ProjectResponse(BaseModel):
    id: str
    name: str
    location: str
    isGlobal: bool = False
    created_at: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language compliance inquiry")
    project_id: str = Field("global", description="Active project workspace ID")
    doc_type: Optional[str] = Field(
        None, description="Optional document type filter (building_code, spec, inspection_report)"
    )


class SourceCard(BaseModel):
    id: str
    documentName: str
    document_name: str
    documentId: str
    document_id: str
    section: str
    section_id: str
    page: int
    page_number: int
    snippet: str
    text: str
    scope: str
    doc_type: str
    category: str
    score: float


class Citation(BaseModel):
    label: str
    scope: str
    documentName: str


class SearchResponse(BaseModel):
    ai_summary: Any
    source_cards: List[SourceCard]
    citations: Optional[List[Citation]] = []


def _map_frontend_category(doc_type: str) -> str:
    """Map internal doc_type to frontend category format."""
    normalized = (doc_type or "").lower()
    if "spec" in normalized:
        return "project-spec"
    if "inspection" in normalized:
        return "inspection-report"
    return "building-code"


# --- Endpoints ---


@app.get("/api/health", tags=["Health"])
def health_check():
    """Health check endpoint confirming service and MongoDB connectivity."""
    db_connected = ping_db()
    return {
        "status": "healthy" if db_connected else "degraded",
        "database_connected": db_connected,
        "service": "BuildSure FastAPI Vector Service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/projects", response_model=ProjectResponse, tags=["Projects"])
def create_or_select_project(payload: ProjectRequest):
    """Create a new project workspace or select an existing one by ID/name."""
    projects_col = get_projects_collection()

    # Query if already exists
    query_filter = {}
    if payload.id:
        query_filter = {"id": payload.id}
    else:
        query_filter = {"name": payload.name}

    existing = projects_col.find_one(query_filter)
    if existing:
        return ProjectResponse(
            id=existing.get("id"),
            name=existing.get("name"),
            location=existing.get("location", ""),
            isGlobal=bool(existing.get("is_global", False)),
            created_at=existing.get("created_at"),
        )

    # Create new project workspace
    project_id = payload.id or f"proj-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    project_record = {
        "id": project_id,
        "name": payload.name,
        "location": payload.location or "",
        "is_global": bool(payload.is_global),
        "created_at": created_at,
    }
    projects_col.insert_one(project_record)

    return ProjectResponse(
        id=project_id,
        name=payload.name,
        location=payload.location or "",
        isGlobal=bool(payload.is_global),
        created_at=created_at,
    )


@app.get("/api/projects", tags=["Projects"])
def list_projects():
    """List all available project workspaces."""
    projects_col = get_projects_collection()
    projects = []
    for p in projects_col.find({}, {"_id": 0}):
        projects.append(
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "location": p.get("location", ""),
                "isGlobal": p.get("is_global", False),
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
    """Upload PDF or text document, parse pages, compute embeddings, and store in Atlas."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    filename = file.filename
    clean_scope = "global" if scope.lower() == "global" or project_id == "global" else "project"
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"

    # Parse file into page structures
    if filename.lower().endswith(".pdf") or file_bytes.startswith(b"%PDF"):
        parsed_doc = load_pdf(
            file_bytes,
            filename=filename,
            project_id=project_id,
            scope=clean_scope,
            doc_type=doc_type,
        )
    else:
        parsed_doc = load_document(
            file_bytes,
            filename=filename,
            project_id=project_id,
            scope=clean_scope,
            doc_type=doc_type,
        )

    parsed_doc["doc_id"] = doc_id
    uploaded_at = datetime.now(timezone.utc).isoformat()

    # Store metadata record in 'documents' collection
    docs_col = get_documents_collection()
    doc_record = {
        "doc_id": doc_id,
        "project_id": project_id,
        "file_name": filename,
        "scope": clean_scope,
        "doc_type": parsed_doc.get("doc_type", doc_type),
        "title": parsed_doc.get("title", filename),
        "page_count": parsed_doc.get("page_count", len(parsed_doc.get("pages", []))),
        "uploaded_at": uploaded_at,
    }
    docs_col.update_one({"doc_id": doc_id}, {"$set": doc_record}, upsert=True)

    # Chunk the document into page-aware vector chunks
    chunks = chunk_document(
        parsed_doc,
        project_id=project_id,
        scope=clean_scope,
        doc_type=doc_record["doc_type"],
    )

    if not chunks:
        return {
            "status": "warning",
            "message": "Document parsed but yielded no text chunks.",
            "doc_id": doc_id,
            "chunks_stored": 0,
        }

    # Generate embeddings
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)

    # Attach embeddings to chunks
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb

    # Insert into 'vector_chunks' collection
    chunks_col = get_chunks_collection()
    chunks_col.insert_many(chunks)

    return {
        "status": "success",
        "doc_id": doc_id,
        "file_name": filename,
        "project_id": project_id,
        "scope": clean_scope,
        "doc_type": doc_record["doc_type"],
        "pages_processed": doc_record["page_count"],
        "chunks_stored": len(chunks),
        "uploaded_at": uploaded_at,
    }


@app.post("/api/search", response_model=SearchResponse, tags=["Search & RAG"])
def search_compliance(payload: SearchRequest):
    """Perform project-aware vector search with pre-filtering and generate strict compliance RAG answer."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty",
        )

    # Retrieve vector chunks matching pre-filter: (scope == "global") OR (project_id == active_project_id)
    try:
        retrieved_chunks = retrieve(
            query=query,
            active_project_id=payload.project_id,
            doc_type_filter=payload.doc_type,
        )
    except Exception as exc:
        logger.error(f"Error during vector retrieval: {exc}")
        retrieved_chunks = []

    # Strict compliance RAG answer via Groq LLM
    rag_result = generate_compliance_answer(query=query, retrieved_chunks=retrieved_chunks)

    # Format source cards for the frontend
    source_cards = []
    for c in retrieved_chunks:
        doc_name = c.get("file_name") or c.get("source") or c.get("title") or "Document"
        d_id = c.get("doc_id") or c.get("id") or ""
        scope_val = "local" if c.get("scope") == "project" else c.get("scope", "global")
        doc_t = c.get("doc_type", "building_code")

        source_cards.append(
            SourceCard(
                id=c.get("id", str(uuid.uuid4())),
                documentName=doc_name,
                document_name=doc_name,
                documentId=d_id,
                document_id=d_id,
                section=c.get("section", "General"),
                section_id=c.get("section_id", ""),
                page=int(c.get("page_number", 1)),
                page_number=int(c.get("page_number", 1)),
                snippet=c.get("text", ""),
                text=c.get("text", ""),
                scope=scope_val,
                doc_type=doc_t,
                category=_map_frontend_category(doc_t),
                score=float(c.get("score", 0.0)),
            )
        )

    citations = [
        Citation(
            label=cite["label"],
            scope=cite["scope"],
            documentName=cite["documentName"],
        )
        for cite in rag_result.get("citations", [])
    ]

    return SearchResponse(
        ai_summary=rag_result.get("answer", ""),
        source_cards=source_cards,
        citations=citations,
    )
