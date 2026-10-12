"""Project-aware vector search backed by MongoDB Atlas Vector Search.

When `$vectorSearch` is unavailable, the same metadata filter is applied with
`find` and the remaining rows are ranked by cosine similarity. Private
documents from other projects are excluded by that filter, not by a prompt.
"""
import logging
import sys
from typing import Callable, Optional

from src.config import TOP_K, VECTOR_INDEX_NAME
from src.db import get_chunks_collection
from src.embedder import embed_query
from src.metadata import resolve_filter_doc_type

logger = logging.getLogger(__name__)


class IndexNotBuiltError(RuntimeError):
    """Raised when the vector index is empty or missing."""


def build_search_filter(active_project_id: str, doc_type_filter: Optional[str] = None) -> dict:
    """Build the pre-filter used by Atlas and by the local cosine fallback.

    (scope == "global") OR (scope == "project" AND project_id == active project)
    AND, when a type is selected, doc_type == that type.
    """
    proj_id = (active_project_id or "global").strip() or "global"
    scope_project_filter = {
        "$or": [
            {"scope": "global"},
            {"$and": [{"scope": "project"}, {"project_id": proj_id}]},
        ]
    }
    canonical_type = resolve_filter_doc_type(doc_type_filter)
    if canonical_type:
        return {"$and": [scope_project_filter, {"doc_type": canonical_type}]}
    return scope_project_filter


def _result_from_doc(doc: dict, score: float) -> dict:
    return {
        "id": doc.get("id", str(doc.get("_id", ""))),
        "doc_id": doc.get("doc_id", ""),
        "source": doc.get("source") or doc.get("file_name", ""),
        "file_name": doc.get("file_name") or doc.get("source", ""),
        "title": doc.get("title", ""),
        "text": doc.get("text", ""),
        "quote": doc.get("quote") or doc.get("text", ""),
        "page_number": doc.get("page_number", 1),
        "page_end": doc.get("page_end", doc.get("page_number", 1)),
        "page_count": doc.get("page_count"),
        "section": doc.get("section", ""),
        "section_id": doc.get("section_id", ""),
        "project_id": doc.get("project_id", ""),
        "scope": doc.get("scope", "global"),
        "doc_type": doc.get("doc_type", "building_code"),
        "score": round(float(score), 4),
    }


def _cosine_fallback(collection, query_vector: list[float], filter_dict: dict, top_k: int) -> list[dict]:
    """Cosine ranking over rows that already match the metadata filter."""
    candidates = list(collection.find(filter_dict))
    if not candidates:
        return []

    def cosine_similarity(left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        norm_left = sum(a * a for a in left) ** 0.5
        norm_right = sum(b * b for b in right) ** 0.5
        if norm_left == 0 or norm_right == 0:
            return 0.0
        return dot / (norm_left * norm_right)

    scored = []
    for doc in candidates:
        embedding = doc.get("embedding")
        if not embedding:
            continue
        scored.append(_result_from_doc(doc, cosine_similarity(query_vector, embedding)))
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def retrieve(
    query: str,
    active_project_id: str = "global",
    doc_type_filter: Optional[str] = None,
    top_k: int = TOP_K,
    collection=None,
    embed_fn: Optional[Callable[[str], list[float]]] = None,
) -> list[dict]:
    """Return the top_k chunks visible to the active project."""
    clean_query = (query or "").strip()
    if not clean_query:
        raise ValueError("Query is empty")

    embed = embed_fn if embed_fn is not None else embed_query
    col = collection if collection is not None else get_chunks_collection()

    total_chunks = col.count_documents({})
    if total_chunks == 0:
        raise IndexNotBuiltError(
            "The search index is empty. Upload documents or run scripts/seed_repository.py."
        )

    query_vec = embed(clean_query)
    filter_expr = build_search_filter(active_project_id, doc_type_filter)
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
                "quote": 1,
                "page_number": 1,
                "page_end": 1,
                "page_count": 1,
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
    except Exception as exc:
        logger.info("Atlas $vectorSearch is unavailable (%s). Ranking filtered rows directly.", type(exc).__name__)
        return _cosine_fallback(col, query_vec, filter_expr, top_k)

    return [_result_from_doc(row, row.get("score", 0.0)) for row in raw_results]


def format_results(results: list[dict]) -> str:
    """Human-readable listing for terminal output."""
    if not results:
        return "No results."
    lines = []
    for index, result in enumerate(results, 1):
        lines.append(
            f"{index}. [{result['score']:.3f}] {result['file_name']} (p.{result['page_number']}) - "
            f"{result['section']} [{result['scope']}/{result['doc_type']}]"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m src.retriever "your question" [project_id] [doc_type]')
        sys.exit(1)
    question = sys.argv[1]
    project = sys.argv[2] if len(sys.argv) > 2 else "global"
    doc_type = sys.argv[3] if len(sys.argv) > 3 else None
    try:
        print(format_results(retrieve(question, active_project_id=project, doc_type_filter=doc_type)))
    except (IndexNotBuiltError, ValueError) as err:
        print(err)
        sys.exit(1)
