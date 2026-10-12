"""Turn text into vectors using a local sentence-transformers model.

The model (all-MiniLM-L6-v2, 384 dimensions) is downloaded once on first use
(~90 MB) and cached by Hugging Face. It runs on CPU and needs no API key.

Vectors are L2-normalised, so cosine similarity equals the dot product.
"""
from functools import lru_cache

from src.config import EMBEDDING_MODEL

BATCH_SIZE = 32


@lru_cache(maxsize=1)
def get_model():
    """Load the embedding model once and reuse it.

    The import is inside the function so that importing this module (and
    running unrelated tests) stays fast and does not need the model.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(texts: list[str], model=None) -> list[list[float]]:
    """Embed a list of strings. Returns one vector (list of floats) per string."""
    if not texts:
        return []
    model = model or get_model()
    vectors = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [list(map(float, v)) for v in vectors]


def embed_query(text: str, model=None) -> list[float]:
    """Embed a single question. Returns one vector."""
    return embed_texts([text], model=model)[0]


if __name__ == "__main__":
    vecs = embed_texts(["minimum rebar spacing for a slab", "fire exit width"])
    print(f"Embedded {len(vecs)} texts, {len(vecs[0])} dimensions each")
    dot = sum(a * b for a, b in zip(vecs[0], vecs[1]))
    print(f"Cosine similarity between the two: {dot:.3f}")
