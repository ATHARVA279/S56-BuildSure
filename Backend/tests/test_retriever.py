"""Tests use a fake store and fake embedder, so no model or database is needed."""
from src.retriever import IndexNotBuiltError, format_results, retrieve


class FakeCollection:
    """Holds (section, embedding) rows; query ranks by cosine distance."""

    def __init__(self, rows):
        self.rows = rows

    def count(self):
        return len(self.rows)

    def query(self, query_embeddings, n_results, include):
        q = query_embeddings[0]
        scored = sorted(
            ((1.0 - sum(a * b for a, b in zip(q, emb)), i, sec) for i, (sec, emb) in enumerate(self.rows)),
            key=lambda r: r[0],
        )[:n_results]
        return {
            "ids": [[f"id{i}" for _, i, _ in scored]],
            "documents": [[f"text of {sec}" for _, _, sec in scored]],
            "metadatas": [[{"source": "doc.txt", "doc_type": "building_code",
                            "section": sec, "section_id": "1"} for _, _, sec in scored]],
            "distances": [[d for d, _, _ in scored]],
        }


ROWS = [("Section 4.2 General", [1.0, 0.0]), ("Clause CW-3 Transfer", [0.0, 1.0]),
        ("Section 7.2 Exit Width", [0.6, 0.8])]


def fake_embed(question):
    return [0.0, 1.0]  # always "looks like" the CW-3 chunk


def test_retrieve_returns_best_match_first():
    results = retrieve("anything", top_k=3, collection=FakeCollection(ROWS), embed_fn=fake_embed)
    assert [r["section"] for r in results] == ["Clause CW-3 Transfer", "Section 7.2 Exit Width", "Section 4.2 General"]
    assert results[0]["score"] == 1.0


def test_retrieve_respects_top_k():
    results = retrieve("anything", top_k=1, collection=FakeCollection(ROWS), embed_fn=fake_embed)
    assert len(results) == 1


def test_empty_question_raises():
    for bad in ["", "   ", None]:
        try:
            retrieve(bad, collection=FakeCollection(ROWS), embed_fn=fake_embed)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_empty_index_raises_helpful_error():
    try:
        retrieve("question", collection=FakeCollection([]), embed_fn=fake_embed)
    except IndexNotBuiltError as err:
        assert "ingest.py" in str(err)
        return
    raise AssertionError("expected IndexNotBuiltError")


def test_question_is_stripped_before_embedding():
    seen = []
    retrieve("  spaced question  ", collection=FakeCollection(ROWS),
             embed_fn=lambda q: seen.append(q) or [0.0, 1.0])
    assert seen == ["spaced question"]


def test_format_results():
    results = retrieve("x", top_k=2, collection=FakeCollection(ROWS), embed_fn=fake_embed)
    text = format_results(results)
    assert text.startswith("1. [1.000] doc.txt - Clause CW-3 Transfer")
    assert format_results([]) == "No results."
