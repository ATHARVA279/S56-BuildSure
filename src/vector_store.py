"""Store chunk vectors in ChromaDB and search them.

ChromaDB runs inside our Python process and saves to disk (chroma_db/), so
there is no server to start. The collection uses cosine distance; we report
similarity as  score = 1 - distance  (1.0 = identical, 0.0 = unrelated).
"""
from src.config import CHROMA_DIR, COLLECTION_NAME

ADD_BATCH_SIZE = 100


def get_collection(path=CHROMA_DIR, name: str = COLLECTION_NAME, reset: bool = False):
    """Open (or create) the persistent collection.

    reset=True deletes any existing collection first, so re-running ingestion
    never leaves duplicate or stale chunks behind.
    """
    import chromadb  # imported here so other modules/tests don't need it

    client = chromadb.PersistentClient(path=str(path))
    if reset:
        try:
            client.delete_collection(name)
        except Exception:
            pass  # nothing to delete on a first run
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def count(collection) -> int:
    """Number of chunks stored."""
    return collection.count()


def add_chunks(collection, chunks: list[dict], embeddings: list[list[float]]) -> int:
    """Store chunks with their embeddings. Returns the number added."""
    if len(chunks) != len(embeddings):
        raise ValueError(f"{len(chunks)} chunks but {len(embeddings)} embeddings")

    for start in range(0, len(chunks), ADD_BATCH_SIZE):
        batch = chunks[start:start + ADD_BATCH_SIZE]
        collection.add(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            embeddings=embeddings[start:start + ADD_BATCH_SIZE],
            metadatas=[
                {
                    "source": c["source"],
                    "doc_type": c["doc_type"],
                    "section": c["section"],
                    "section_id": c["section_id"],
                }
                for c in batch
            ],
        )
    return len(chunks)


def query(collection, query_embedding: list[float], top_k: int = 4) -> list[dict]:
    """Return the top_k most similar chunks, best first.

    Each result: {id, text, source, doc_type, section, section_id, score}.
    Returns [] if the collection is empty.
    """
    total = collection.count()
    if total == 0:
        return []

    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, total),
        include=["documents", "metadatas", "distances"],
    )

    results = []
    for chunk_id, text, meta, dist in zip(
        raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    ):
        results.append({
            "id": chunk_id,
            "text": text,
            "source": meta["source"],
            "doc_type": meta["doc_type"],
            "section": meta["section"],
            "section_id": meta["section_id"],
            "score": round(1.0 - dist, 4),
        })
    return results
