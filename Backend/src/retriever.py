"""Project-aware vector search backed by MongoDB Atlas Vector Search."""
import logging
import sys
from typing import Callable, Optional

from src.config import TOP_K, VECTOR_INDEX_NAME
from src.db import get_chunks_collection
from src.embedder import embed_query

logger = logging.getLogger(__name__)


class IndexNotBuiltError(RuntimeError):
    """Raised when the vector index is empty or missing."""


def _normalize_doc_type(raw_type: Optional[str]) -> Optional[str]:
    """Map filters like 'project-specs' or 'building-codes' to canonical labels."""
    if not raw_type or raw_type == "all":
        return None
    cleaned = raw_type.strip().lower()
    mapping = {
        "building-code": "building_code",
        "building-codes": "building_code",
        "building code": "building_code",
        "building_code": "building_code",
        "project-spec": "spec",
        "project-specs": "spec",
        "specification": "spec",
        "project specification": "spec",
        "spec": "spec",
        "inspection-report": "inspection_report",
        "inspection-reports": "inspection_report",
        "inspection report": "inspection_report",
        "inspection": "inspection_report",
        "inspection_report": "inspection_report",
    }
    return mapping.get(cleaned, cleaned)


def build_search_filter(active_project_id: str, doc_type_filter: Optional[str] = None) -> dict:
    """Build the MongoDB Atlas Vector Search pre-filter.

    Filter: (scope == "global") OR (project_id == active_project_id)
    If doc_type_filter is present: (scope == "global" OR project_id == active_project_id) AND (doc_type == doc_type_filter)
    """
    proj_id = active_project_id or "global"
    scope_project_filter = {
        "$or": [
            {"scope": "global"},
            {"project_id": proj_id},
        ]
    }

    canonical_type = _normalize_doc_type(doc_type_filter)
    if canonical_type:
        return {
            "$and": [
                scope_project_filter,
                {"doc_type": canonical_type},
            ]
        }
    return scope_project_filter


def _cosine_fallback(
    collection,
    query_vector: list[float],
    filter_dict: dict,
    top_k: int,
) -> list[dict]:
    """In-memory cosine similarity fallback when Atlas $vectorSearch is unavailable."""
    candidates = list(collection.find(filter_dict))
    if not candidates:
        return []

    def cosine_similarity(v1: list[float], v2: list[float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    scored = []
    for doc in candidates:
        emb = doc.get("embedding")
        if not emb:
            continue
        score = cosine_similarity(query_vector, emb)
        item = {
            "id": doc.get("id", str(doc.get("_id"))),
            "doc_id": doc.get("doc_id", ""),
            "source": doc.get("source") or doc.get("file_name", ""),
            "file_name": doc.get("file_name") or doc.get("source", ""),
            "title": doc.get("title", ""),
            "text": doc.get("text", ""),
            "page_number": doc.get("page_number", 1),
            "section": doc.get("section", ""),
            "section_id": doc.get("section_id", ""),
            "project_id": doc.get("project_id", ""),
            "scope": doc.get("scope", "global"),
            "doc_type": doc.get("doc_type", "building_code"),
            "score": round(float(score), 4),
        }
        scored.append(item)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def retrieve(
    query: str,
    active_project_id: str = "global",
    doc_type_filter: Optional[str] = None,
    top_k: int = TOP_K,
    collection=None,
    embed_fn: Callable[[str], list[float]] = embed_query,
) -> list[dict]:
    """Retrieve the top_k chunks most relevant to the query with project-aware pre-filtering.

    Pipeline:
      1. Embed query
      2. Construct MongoDB Atlas $vectorSearch aggregation pipeline with pre-filtering:
         Filter: (scope == "global") OR (project_id == active_project_id)
         and optional (doc_type == doc_type_filter)
    """
    clean_query = (query or "").strip()
    if not clean_query:
        raise ValueError("Query is empty")

    col = collection if collection is not None else get_chunks_collection()

    total_chunks = col.count_documents({})
    if total_chunks == 0:
        raise IndexNotBuiltError("The search index is empty in MongoDB.")

    query_vec = embed_fn(clean_query)
    filter_expr = build_search_filter(active_project_id, doc_type_filter)

    # MongoDB Atlas $vectorSearch pipeline
    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vec,
                "numCandidates": max(top_k * 10, 50),
                "limit": top_k,
                "filter": filter_expr,
            }
        },
        {
            "$project": {
                "_id": 0,
                "id": 1,
                "doc_id": 1,
                "source": 1,
                "file_name": 1,
                "title": 1,
                "text": 1,
                "page_number": 1,
                "section": 1,
                "section_id": 1,
                "project_id": 1,
                "scope": 1,
                "doc_type": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    try:
        raw_results = list(col.aggregate(pipeline))
        results = []
        for r in raw_results:
            results.append({
                "id": r.get("id", ""),
                "doc_id": r.get("doc_id", ""),
                "source": r.get("source") or r.get("file_name", ""),
                "file_name": r.get("file_name") or r.get("source", ""),
                "title": r.get("title", ""),
                "text": r.get("text", ""),
                "page_number": r.get("page_number", 1),
                "section": r.get("section", ""),
                "section_id": r.get("section_id", ""),
                "project_id": r.get("project_id", ""),
                "scope": r.get("scope", "global"),
                "doc_type": r.get("doc_type", "building_code"),
                "score": round(float(r.get("score", 0.0)), 4),
            })
        return results
    except Exception as exc:
        logger.info(
            f"Atlas $vectorSearch aggregation fallback engaged ({exc}). Using direct vector comparison."
        )
        return _cosine_fallback(col, query_vec, filter_expr, top_k)


def format_results(results: list[dict]) -> str:
    """Human-readable listing for terminal output."""
    if not results:
        return "No results."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. [{r['score']:.3f}] {r['file_name']} (p.{r['page_number']}) - "
            f"{r['section']} [{r['scope']}/{r['doc_type']}]"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m src.retriever "your question" [project_id] [doc_type]')
        sys.exit(1)
    q = sys.argv[1]
    proj = sys.argv[2] if len(sys.argv) > 2 else "global"
    dtype = sys.argv[3] if len(sys.argv) > 3 else None
    try:
        print(format_results(retrieve(q, active_project_id=proj, doc_type_filter=dtype)))
    except (IndexNotBuiltError, ValueError) as err:
        print(err)
        sys.exit(1)
