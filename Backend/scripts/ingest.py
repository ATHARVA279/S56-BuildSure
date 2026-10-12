"""Build the search index: load -> chunk -> embed -> store.

Usage (from the repo root):
    python scripts/ingest.py

Re-running is safe: the collection is wiped and rebuilt each time, so you never
get duplicate chunks. Run it again whenever you add or edit documents.
"""
import sys
import time
from pathlib import Path

# Make `import src...` work when run as `python scripts/ingest.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chunker import chunk_documents  # noqa: E402
from src.config import CHROMA_DIR, DOCS_DIR  # noqa: E402
from src.embedder import embed_texts  # noqa: E402
from src.loader import load_documents  # noqa: E402
from src.vector_store import add_chunks, count, get_collection  # noqa: E402


def ingest(docs_dir=DOCS_DIR, chroma_dir=CHROMA_DIR, embed_fn=embed_texts, collection=None) -> dict:
    """Run the full ingestion pipeline and return a summary.

    embed_fn and collection can be injected (used by the tests); in normal use
    they default to the real embedder and a fresh on-disk ChromaDB collection.
    """
    start = time.time()

    docs = load_documents(docs_dir)
    if not docs:
        raise ValueError(f"No .txt documents found in {docs_dir}")

    chunks = chunk_documents(docs)
    if not chunks:
        raise ValueError("Documents were loaded but produced no chunks")

    embeddings = embed_fn([c["text"] for c in chunks])

    if collection is None:
        collection = get_collection(path=chroma_dir, reset=True)
    add_chunks(collection, chunks, embeddings)

    return {
        "documents": len(docs),
        "chunks": len(chunks),
        "stored": count(collection),
        "seconds": round(time.time() - start, 1),
    }


def main() -> int:
    print(f"Reading documents from {DOCS_DIR}")
    print("Embedding chunks (the first run downloads the model, ~90 MB)...")
    try:
        summary = ingest()
    except (FileNotFoundError, ValueError) as err:
        print(f"Ingestion failed: {err}")
        return 1
    print(
        f"Done: {summary['documents']} documents -> {summary['chunks']} chunks "
        f"-> {summary['stored']} stored in {summary['seconds']}s"
    )
    print(f"Index saved to {CHROMA_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
