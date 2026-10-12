from src.chunker import chunk_document, chunk_documents

DOC = {
    "source": "building_code_x.txt",
    "title": "SAMPLE CODE",
    "doc_type": "building_code",
    "text": (
        "SAMPLE CODE\nDocument type: building code\n\n"
        "Section 1.1 Scope\nApplies to all slabs.\n\n"
        "Section 1.2 Spacing\nSpacing shall not exceed 200 mm.\n\n"
        "Clause CW-3 Override\nSpacing shall not exceed 150 mm.\n"
    ),
}


def test_one_chunk_per_clause():
    chunks = chunk_document(DOC)
    assert [c["section_id"] for c in chunks] == ["1.1", "1.2", "CW-3"]


def test_chunk_keeps_metadata_and_clause_text():
    c = chunk_document(DOC)[1]
    assert c["source"] == "building_code_x.txt"
    assert c["doc_type"] == "building_code"
    assert c["section"] == "Section 1.2 Spacing"
    assert "200 mm" in c["text"] and "150 mm" not in c["text"]
    assert c["id"] == "building_code_x__chunk_001"


def test_long_clause_is_split_with_overlap():
    long_doc = dict(DOC, text="Section 9.1 Long\n" + " ".join(f"w{i}" for i in range(100)))
    chunks = chunk_document(long_doc, size=40, overlap=10)
    assert len(chunks) == 3
    assert "w99" in chunks[-1]["text"]  # nothing dropped at the end
    first_words = chunks[0]["text"].split()[-40:]
    second_words = chunks[1]["text"].split()
    assert first_words[-10:] == second_words[-40:-30]  # 10-word overlap
    assert all(c["section_id"] == "9.1" for c in chunks)


def test_no_headings_falls_back_to_whole_text():
    plain = {"source": "notes.txt", "title": "NOTES", "doc_type": "unknown", "text": "NOTES\nJust some text."}
    chunks = chunk_document(plain)
    assert len(chunks) == 1 and "Just some text." in chunks[0]["text"]


def test_sample_docs_chunk_into_clauses():
    from src.loader import load_documents
    docs = load_documents()
    chunks = chunk_documents(docs)
    assert len(chunks) > len(docs)
    assert all(c["section"] and c["text"] for c in chunks)
    assert len({c["id"] for c in chunks}) == len(chunks)  # ids are unique
