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
    long_doc = dict(
        DOC, text="Section 9.1 Long\n" + " ".join(f"w{i}" for i in range(100))
    )
    chunks = chunk_document(long_doc, size=40, overlap=10)
    assert len(chunks) == 3
    assert "w99" in chunks[-1]["text"]  # nothing dropped at the end
    first_words = chunks[0]["text"].split()[-40:]
    second_words = chunks[1]["text"].split()
    assert first_words[-10:] == second_words[-40:-30]  # 10-word overlap
    assert all(c["section_id"] == "9.1" for c in chunks)


def test_no_headings_falls_back_to_whole_text():
    plain = {
        "source": "notes.txt",
        "title": "NOTES",
        "doc_type": "unknown",
        "text": "NOTES\nJust some text.",
    }
    chunks = chunk_document(plain)
    assert len(chunks) == 1 and "Just some text." in chunks[0]["text"]


def test_sample_docs_chunk_into_clauses():
    from src.loader import load_documents

    docs = load_documents()
    chunks = chunk_documents(docs)
    assert len(chunks) > len(docs)
    assert all(c["section"] and c["text"] for c in chunks)
    assert len({c["id"] for c in chunks}) == len(chunks)  # ids are unique


def test_default_windows_are_about_400_words_with_50_word_overlap():
    from src.config import CHUNK_OVERLAP, CHUNK_SIZE

    assert CHUNK_SIZE == 400 and CHUNK_OVERLAP == 50
    words = " ".join(f"w{i}" for i in range(450))
    doc = {
        "source": "t.txt",
        "title": "T",
        "doc_type": "building_code",
        "text": "Section 1.1 Long\n" + words,
    }
    chunks = chunk_document(doc)
    assert len(chunks) == 2
    assert chunks[0]["quote"].split()[-50:] == chunks[1]["quote"].split()[:50]


def test_numbered_heading_without_the_word_section():
    doc = {
        "source": "code.txt",
        "title": "CODE",
        "doc_type": "building_code",
        "text": "1005.1 Minimum Width\nNot less than 44 inches.",
    }
    chunks = chunk_document(doc)
    assert chunks[0]["section_id"] == "1005.1"
    assert "44 inches" in chunks[0]["quote"]


def test_empty_page_does_not_renumber_following_page():
    doc = {
        "source": "code.pdf",
        "file_name": "code.pdf",
        "doc_id": "code",
        "title": "CODE",
        "doc_type": "building_code",
        "page_count": 3,
        "pages": [
            {"page_number": 1, "text": "Section 1.1 First\nAlpha rule."},
            {"page_number": 2, "text": "   "},
            {"page_number": 3, "text": "Section 1.2 Second\nBeta rule."},
        ],
    }
    chunks = chunk_document(doc)
    by_id = {chunk["section_id"]: chunk for chunk in chunks}
    assert by_id["1.1"]["page_number"] == 1
    assert by_id["1.2"]["page_number"] == 3
    assert all(chunk["page_number"] != 2 for chunk in chunks)


def test_inline_section_reference_stays_inside_the_finding():
    doc = {
        "source": "report.txt",
        "title": "REPORT",
        "doc_type": "inspection_report",
        "text": (
            "Finding B-1 Rebar Spacing\n"
            "Measured at 175 mm.\n"
            "Section 4.2 of the code still applies. Status: open.\n"
        ),
    }
    chunks = chunk_document(doc)
    assert [chunk["section_id"] for chunk in chunks] == ["B-1"]
    assert "Status: open" in chunks[0]["quote"]
    assert "Section 4.2 of the code" in chunks[0]["quote"]


def test_section_continuing_onto_the_next_page_keeps_its_id():
    doc = {
        "source": "code.pdf",
        "file_name": "code.pdf",
        "title": "CODE",
        "doc_type": "building_code",
        "page_count": 2,
        "pages": [
            {
                "page_number": 1,
                "text": "Section 7.2 Exit Width\nThe clear width shall be at least 1.0 m.",
            },
            {
                "page_number": 2,
                "text": "Measured at the narrowest point.\nSection 7.3 Travel\nMaximum 30 m.",
            },
        ],
    }
    chunks = chunk_document(doc)
    continued = [
        chunk
        for chunk in chunks
        if chunk["section_id"] == "7.2" and chunk["page_number"] == 2
    ]
    assert continued and "narrowest" in continued[0]["quote"]
    travel = [chunk for chunk in chunks if chunk["section_id"] == "7.3"]
    assert travel[0]["page_number"] == 2
