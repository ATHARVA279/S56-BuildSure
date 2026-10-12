"""Tests use a fake model so they run instantly and offline."""
import sys

import numpy as np

from src.embedder import embed_query, embed_texts


class FakeModel:
    """Mimics SentenceTransformer.encode: returns a (n, 4) array."""

    def __init__(self):
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append(kwargs)
        return np.array([[float(len(t)), 0.0, 1.0, 2.0] for t in texts])


def test_one_vector_per_text():
    vecs = embed_texts(["ab", "abcd", "abcdef"], model=FakeModel())
    assert len(vecs) == 3
    assert all(len(v) == 4 for v in vecs)
    assert vecs[1][0] == 4.0


def test_returns_plain_python_floats():
    vecs = embed_texts(["abc"], model=FakeModel())
    assert isinstance(vecs[0], list) and isinstance(vecs[0][0], float)


def test_empty_input_returns_empty_without_loading_model():
    assert embed_texts([]) == []


def test_embed_query_returns_single_flat_vector():
    vec = embed_query("slab", model=FakeModel())
    assert len(vec) == 4 and not isinstance(vec[0], list)


def test_requests_normalised_embeddings():
    fake = FakeModel()
    embed_texts(["x"], model=fake)
    assert fake.calls[0]["normalize_embeddings"] is True


def test_importing_module_does_not_load_sentence_transformers():
    assert "sentence_transformers" not in sys.modules
