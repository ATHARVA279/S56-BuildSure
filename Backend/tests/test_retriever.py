"""Retriever tests use an in-memory collection, so no model or database is needed."""
from src.local_store import MemoryCollection
from src.retriever import IndexNotBuiltError, format_results, retrieve


def make_row(section, section_id, embedding):
    return {
        "id": section_id,
        "doc_id": "doc",
        "source": "doc.txt",
        "file_name": "doc.txt",
        "title": "Doc",
        "text": f"text of {section}",
        "quote": f"text of {section}",
        "page_number": 1,
        "section": section,
        "section_id": section_id,
        "project_id": "global",
        "scope": "global",
        "doc_type": "building_code",
        "embedding": embedding,
    }


ROWS = [
    make_row("Section 4.2 General", "4.2", [1.0, 0.0]),
    make_row("Clause CW-3 Transfer", "CW-3", [0.0, 1.0]),
    make_row("Section 7.2 Exit Width", "7.2", [0.6, 0.8]),
]


def collection_with(rows):
    collection = MemoryCollection()
    if rows:
        collection.insert_many(rows)
    return collection


def fake_embed(question):
    return [0.0, 1.0]


def test_retrieve_returns_best_match_first():
    results = retrieve(
        "anything",
        top_k=3,
        collection=collection_with(ROWS),
        embed_fn=fake_embed,
    )
    assert [row["section"] for row in results] == [
        "Clause CW-3 Transfer",
        "Section 7.2 Exit Width",
        "Section 4.2 General",
    ]
    assert results[0]["score"] == 1.0


def test_retrieve_respects_top_k():
    results = retrieve("anything", top_k=1, collection=collection_with(ROWS), embed_fn=fake_embed)
    assert len(results) == 1


def test_empty_question_raises():
    for bad in ["", "   ", None]:
        try:
            retrieve(bad, collection=collection_with(ROWS), embed_fn=fake_embed)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_empty_index_raises_helpful_error():
    try:
        retrieve("question", collection=collection_with([]), embed_fn=fake_embed)
    except IndexNotBuiltError as err:
        assert "empty" in str(err).lower()
        return
    raise AssertionError("expected IndexNotBuiltError")


def test_question_is_stripped_before_embedding():
    seen = []
    retrieve(
        "  spaced question  ",
        collection=collection_with(ROWS),
        embed_fn=lambda question: seen.append(question) or [0.0, 1.0],
    )
    assert seen == ["spaced question"]


def test_format_results():
    results = retrieve("x", top_k=2, collection=collection_with(ROWS), embed_fn=fake_embed)
    text = format_results(results)
    assert text.startswith("1. [1.000] doc.txt (p.1) - Clause CW-3 Transfer")
    assert format_results([]) == "No results."


def test_other_project_documents_are_excluded():
    collection = MemoryCollection()
    collection.insert_many([
        {
            **make_row("Alpha spec", "A-1", [0.0, 1.0]),
            "id": "alpha",
            "scope": "project",
            "project_id": "alpha",
            "doc_type": "spec",
            "file_name": "alpha.pdf",
        },
        {
            **make_row("Beta spec", "B-1", [0.0, 1.0]),
            "id": "beta",
            "scope": "project",
            "project_id": "beta",
            "doc_type": "spec",
            "file_name": "beta.pdf",
        },
        make_row("Global code", "7.2", [1.0, 0.0]),
    ])
    results = retrieve(
        "spec",
        active_project_id="alpha",
        top_k=10,
        collection=collection,
        embed_fn=lambda question: [0.0, 1.0],
    )
    names = {row["file_name"] for row in results}
    assert "alpha.pdf" in names
    assert "beta.pdf" not in names


def test_document_type_filter_limits_rows():
    collection = MemoryCollection()
    collection.insert_many([
        make_row("Code", "1.1", [1.0, 0.0]),
        {
            **make_row("Spec", "CW-1", [1.0, 0.0]),
            "id": "spec",
            "doc_type": "spec",
            "file_name": "spec.pdf",
            "scope": "project",
            "project_id": "alpha",
        },
    ])
    results = retrieve(
        "width",
        active_project_id="alpha",
        doc_type_filter="building_code",
        top_k=10,
        collection=collection,
        embed_fn=lambda question: [1.0, 0.0],
    )
    assert [row["file_name"] for row in results] == ["doc.txt"]
