import pytest

from src.loader import load_document, load_documents


def test_load_document_reads_metadata(tmp_path):
    f = tmp_path / "building_code_x.txt"
    f.write_text("MY CODE TITLE\nDocument type: building code\n\nSection 1.1 Test\nBody.", encoding="utf-8")
    doc = load_document(f)
    assert doc["source"] == "building_code_x.txt"
    assert doc["title"] == "MY CODE TITLE"
    assert doc["doc_type"] == "building_code"
    assert "Section 1.1" in doc["text"]


def test_doc_type_falls_back_to_filename(tmp_path):
    f = tmp_path / "inspection_report_z.txt"
    f.write_text("A report with no type header\nFinding 1.", encoding="utf-8")
    assert load_document(f)["doc_type"] == "inspection_report"


def test_load_documents_only_txt_sorted_and_skips_empty(tmp_path):
    (tmp_path / "b.txt").write_text("Second doc", encoding="utf-8")
    (tmp_path / "a.txt").write_text("First doc", encoding="utf-8")
    (tmp_path / "empty.txt").write_text("   \n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("ignored", encoding="utf-8")
    docs = load_documents(tmp_path)
    assert [d["source"] for d in docs] == ["a.txt", "b.txt"]


def test_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_documents(tmp_path / "does_not_exist")


def test_sample_docs_load():
    docs = load_documents()
    assert len(docs) >= 1
    assert all(d["text"] and d["source"].endswith(".txt") for d in docs)
