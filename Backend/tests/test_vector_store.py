"""Tests use a fake in-memory collection so they run offline and instantly."""
import sys

from src.vector_store import add_chunks, count, query


class FakeCollection:
    """Mimics the parts of a Chroma collection we use (cosine distance)."""

    def __init__(self):
        self.rows = []  # (id, doc, meta, embedding)
        self.add_calls = 0

    def add(self, ids, documents, embeddings, metadatas):
        self.add_calls += 1
        self.rows.extend(zip(ids, documents, metadatas, embeddings))

    def count(self):
        return len(self.rows)

    def query(self, query_embeddings, n_results, include):
        q = query_embeddings[0]
        scored = []
        for cid, doc, meta, emb in self.rows:
            dot = sum(a * b for a, b in zip(q, emb))
            scored.append((1.0 - dot, cid, doc, meta))
        scored.sort(key=lambda r: r[0])
        top = scored[:n_results]
        return {
            "ids": [[r[1] for r in top]],
            "documents": [[r[2] for r in top]],
            "metadatas": [[r[3] for r in top]],
            "distances": [[r[0] for r in top]],
        }


def make_chunk(i, section="Section 1.1 Test"):
    return {"id": f"doc__chunk_{i:03d}", "text": f"text {i}", "source": "doc.txt",
            "doc_type": "building_code", "section": section, "section_id": "1.1"}


def test_add_and_count():
    col = FakeCollection()
    n = add_chunks(col, [make_chunk(0), make_chunk(1)], [[1.0, 0.0], [0.0, 1.0]])
    assert n == 2 and count(col) == 2


def test_add_rejects_mismatched_lengths():
    try:
        add_chunks(FakeCollection(), [make_chunk(0)], [])
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_add_batches_large_inputs():
    col = FakeCollection()
    chunks = [make_chunk(i) for i in range(250)]
    add_chunks(col, chunks, [[1.0, 0.0]] * 250)
    assert col.add_calls == 3 and count(col) == 250


def test_stores_expected_metadata_keys():
    col = FakeCollection()
    add_chunks(col, [make_chunk(0)], [[1.0, 0.0]])
    assert set(col.rows[0][2]) == {"source", "doc_type", "section", "section_id"}


def test_query_returns_best_first_with_scores():
    col = FakeCollection()
    add_chunks(col, [make_chunk(0, "A"), make_chunk(1, "B"), make_chunk(2, "C")],
               [[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]])
    results = query(col, [0.0, 1.0], top_k=2)
    assert [r["section"] for r in results] == ["B", "C"]
    assert results[0]["score"] == 1.0
    assert results[0]["score"] > results[1]["score"]
    assert {"id", "text", "source", "doc_type", "section", "section_id", "score"} <= set(results[0])


def test_query_empty_collection_returns_empty_list():
    assert query(FakeCollection(), [1.0, 0.0]) == []


def test_top_k_larger_than_collection_is_clamped():
    col = FakeCollection()
    add_chunks(col, [make_chunk(0)], [[1.0, 0.0]])
    assert len(query(col, [1.0, 0.0], top_k=10)) == 1


def test_importing_module_does_not_load_chromadb():
    assert "chromadb" not in sys.modules
