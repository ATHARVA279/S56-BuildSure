"""Find the chunks most relevant to a question.

    results = retrieve("What rebar spacing applies to the transfer slab?")

Each result is a dict: {id, text, source, doc_type, section, section_id, score}
ordered best first. `score` is cosine similarity (1.0 = identical).

Try it from the terminal (after running scripts/ingest.py):
    python -m src.retriever "minimum width of a fire exit"
"""
import sys

from src.config import TOP_K
from src.embedder import embed_query
from src.vector_store import count, get_collection, query


class IndexNotBuiltError(RuntimeError):
    """Raised when the vector index is empty or missing."""


def retrieve(question: str, top_k: int = TOP_K, collection=None, embed_fn=embed_query) -> list[dict]:
    """Return the top_k chunks most similar to the question, best first.

    collection and embed_fn can be injected (used by tests); by default the
    on-disk ChromaDB collection and the real embedding model are used.
    """
    question = (question or "").strip()
    if not question:
        raise ValueError("Question is empty")

    if collection is None:
        collection = get_collection(reset=False)
    if count(collection) == 0:
        raise IndexNotBuiltError("The search index is empty. Run: python scripts/ingest.py")

    return query(collection, embed_fn(question), top_k=top_k)


def format_results(results: list[dict]) -> str:
    """Human-readable listing for the terminal."""
    if not results:
        return "No results."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r['score']:.3f}] {r['source']} - {r['section']}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m src.retriever "your question"')
        sys.exit(1)
    try:
        print(format_results(retrieve(" ".join(sys.argv[1:]))))
    except (IndexNotBuiltError, ValueError) as err:
        print(err)
        sys.exit(1)
