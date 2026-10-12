"""API tests use the in-memory store and a keyword embedder. No Atlas or Groq calls."""

import json

import pytest
from fastapi.testclient import TestClient

from src.config import EMBEDDING_DIM
from src.db import ATLAS_VECTOR_INDEX_DEFINITION
from src.main import app
from src.pdf_util import blank_pdf, build_pdf_pages
from src.rag import NO_EVIDENCE

TOKENS = {
    "EXITWIDTHTOKEN": 0,
    "REBARTOKEN": 1,
    "CLOSEDTOKEN": 2,
    "UNVERIFIEDTOKEN": 3,
    "BETAONLYTOKEN": 4,
    "SPECWIDTHTOKEN": 5,
}


def vector_for(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    hits = [index for token, index in TOKENS.items() if token in text]
    if not hits:
        vector[10] = 1.0
    else:
        for index in hits:
            vector[index] = 1.0
    norm = sum(value * value for value in vector) ** 0.5
    return [value / norm for value in vector]


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(
        "src.main.embed_texts", lambda texts: [vector_for(text) for text in texts]
    )
    monkeypatch.setattr("src.retriever.embed_query", vector_for)
    with TestClient(app) as client:
        yield client


def create_project(api, name="Project Alpha", location="Site 44"):
    response = api.post(
        "/api/projects", json={"project_name": name, "location": location}
    )
    assert response.status_code == 200, response.text
    return response.json()


def upload(api, filename, pages, **fields):
    response = api.post(
        "/api/documents/upload",
        files={"file": (filename, build_pdf_pages(pages), "application/pdf")},
        data=fields,
    )
    return response


def test_vector_index_definition_matches_embedding_and_filters():
    fields = ATLAS_VECTOR_INDEX_DEFINITION["definition"]["fields"]
    vector = next(field for field in fields if field["type"] == "vector")
    filters = {field["path"] for field in fields if field["type"] == "filter"}
    assert vector["numDimensions"] == EMBEDDING_DIM == 384
    assert vector["path"] == "embedding"
    assert {"project_id", "scope", "doc_type"} <= filters


def test_create_project_returns_id_and_timestamp(api):
    created = create_project(api)
    assert created["id"].startswith("proj-")
    assert created["name"] == "Project Alpha"
    assert created["location"] == "Site 44"
    assert created["created_at"]
    listed = api.get("/api/projects").json()
    assert any(project["id"] == created["id"] for project in listed)


def test_same_display_name_creates_distinct_projects(api):
    first = create_project(api, "Tower")
    second = create_project(api, "Tower")
    assert first["id"] != second["id"]


def test_invalid_project_request_is_rejected(api):
    response = api.post("/api/projects", json={"location": "Site 44"})
    assert response.status_code == 422


def test_upload_validation_and_failed_records_are_not_indexed(api, monkeypatch):
    project = create_project(api)
    not_pdf = api.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={
            "project_id": project["id"],
            "scope": "project",
            "doc_type": "building_code",
        },
    )
    assert not_pdf.status_code == 400

    empty = api.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={
            "project_id": project["id"],
            "scope": "project",
            "doc_type": "building_code",
        },
    )
    assert empty.status_code == 400

    malformed = api.post(
        "/api/documents/upload",
        files={"file": ("bad.pdf", b"%PDF-1.4\nthis is not a pdf", "application/pdf")},
        data={
            "project_id": project["id"],
            "scope": "project",
            "doc_type": "building_code",
        },
    )
    assert malformed.status_code in {400, 422}

    scanned = api.post(
        "/api/documents/upload",
        files={"file": ("scan.pdf", blank_pdf(), "application/pdf")},
        data={
            "project_id": project["id"],
            "scope": "project",
            "doc_type": "building_code",
        },
    )
    assert scanned.status_code == 422
    assert "OCR is not implemented" in scanned.json()["detail"]

    missing = upload(
        api,
        "orphan.pdf",
        ["Section 1.1 Orphan\nEXITWIDTHTOKEN text"],
        project_id="proj-missing",
        scope="project",
        doc_type="building_code",
    )
    assert missing.status_code == 404

    bad_type = upload(
        api,
        "novel.pdf",
        ["Section 1.1 X\nEXITWIDTHTOKEN text"],
        project_id=project["id"],
        scope="project",
        doc_type="novel",
    )
    assert bad_type.status_code == 400

    monkeypatch.setattr("src.ingestion.MAX_UPLOAD_BYTES", 40)
    too_big = api.post(
        "/api/documents/upload",
        files={"file": ("big.pdf", b"%PDF" + b"x" * 80, "application/pdf")},
        data={
            "project_id": project["id"],
            "scope": "project",
            "doc_type": "building_code",
        },
    )
    assert too_big.status_code == 413
    monkeypatch.setattr("src.ingestion.MAX_UPLOAD_BYTES", 25 * 1024 * 1024)

    monkeypatch.setattr(
        "src.main.embed_texts",
        lambda texts: [[0.1, 0.2] for _ in texts],
    )
    bad_vectors = upload(
        api,
        "dims.pdf",
        ["Section 1.1 Dim\nEXITWIDTHTOKEN width"],
        project_id=project["id"],
        scope="project",
        doc_type="building_code",
    )
    assert bad_vectors.status_code == 500

    documents = api.get("/api/documents", params={"project_id": project["id"]}).json()
    assert documents
    assert all(document["processing_status"] != "indexed" for document in documents)
    assert not any(document["name"] == "notes.txt" for document in documents)


def test_search_workflow_citations_filters_isolation_and_deficiencies(api):
    alpha = create_project(api, "Project Alpha", "Site 44")
    beta = create_project(api, "Project Beta", "Site 12")

    global_doc = upload(
        api,
        "fire_code.pdf",
        [
            "Section 1.1 Exit Width\nEXITWIDTHTOKEN The clear width shall be at least 1.0 m.",
            "Section 2.4 Rebar\nREBARTOKEN Maximum spacing is 150 mm.",
        ],
        project_id=alpha["id"],
        scope="global",
        doc_type="building_code",
    )
    assert global_doc.status_code == 200, global_doc.text
    assert global_doc.json()["project_id"] == "global"
    assert global_doc.json()["pages_processed"] == 2

    spec = upload(
        api,
        "alpha_spec.pdf",
        [
            "Section 8.1 Corridor\nSPECWIDTHTOKEN Project corridor minimum is stated here."
        ],
        project_id=alpha["id"],
        scope="project",
        doc_type="specification",
    )
    assert spec.status_code == 200, spec.text
    assert spec.json()["doc_type"] == "spec"

    opened = upload(
        api,
        "alpha_inspection.pdf",
        [
            "Finding B-1 Width\nEXITWIDTHTOKEN measured below the stated width. Status: open."
        ],
        project_id=alpha["id"],
        scope="project",
        doc_type="inspection_report",
    )
    assert opened.status_code == 200, opened.text

    closed = upload(
        api,
        "alpha_closed.pdf",
        ["Finding B-2 Cover\nCLOSEDTOKEN cover meets the clause. Status: closed."],
        project_id=alpha["id"],
        scope="project",
        doc_type="inspection_report",
    )
    assert closed.status_code == 200, closed.text

    unverified = upload(
        api,
        "alpha_unverified.pdf",
        ["Finding C-1 Joint\nUNVERIFIEDTOKEN DEFICIENCY noted at the joint."],
        project_id=alpha["id"],
        scope="project",
        doc_type="inspection_report",
    )
    assert unverified.status_code == 200, unverified.text

    secret = upload(
        api,
        "beta_secret.pdf",
        ["Section 9.1 Hidden\nBETAONLYTOKEN this belongs only to beta."],
        project_id=beta["id"],
        scope="project",
        doc_type="specification",
    )
    assert secret.status_code == 200, secret.text

    listed = api.get("/api/documents", params={"project_id": alpha["id"]}).json()
    names = {document["name"] for document in listed}
    assert "fire_code.pdf" in names
    assert "alpha_spec.pdf" in names
    assert "beta_secret.pdf" not in names

    width = api.post(
        "/api/search",
        json={
            "query": "What does EXITWIDTHTOKEN require?",
            "project_id": alpha["id"],
            "doc_type_filter": "All",
        },
    )
    assert width.status_code == 200, width.text
    body = width.json()
    assert body["has_deficiency"] is True
    assert body["deficiency_text"].startswith("DEFICIENCY DETECTED")
    assert "alpha_inspection.pdf" in body["deficiency_text"]
    assert "Status: open" in body["deficiency_text"]
    cards = body["source_cards"]
    code_cards = [card for card in cards if card["doc_name"] == "fire_code.pdf"]
    assert code_cards
    assert code_cards[0]["page_number"] == 1
    assert "1.0 m" in code_cards[0]["quote"]
    assert "fire_code.pdf, 1.1, Page 1" in body["ai_summary"]
    assert "complies" not in body["ai_summary"].lower()
    assert body["generation_mode"] == "extractive"
    assert "GROQ_API_KEY" in (body["retrieval_note"] or "")

    file_response = api.get(code_cards[0]["pdf_url"].split("#")[0])
    assert file_response.status_code == 200
    assert file_response.content.startswith(b"%PDF")

    codes_only = api.post(
        "/api/search",
        json={
            "query": "EXITWIDTHTOKEN",
            "project_id": alpha["id"],
            "doc_type_filter": "building_code",
        },
    ).json()
    assert codes_only["has_deficiency"] is False
    assert {card["doc_name"] for card in codes_only["source_cards"]} == {
        "fire_code.pdf"
    }

    rebar = api.post(
        "/api/search",
        json={
            "query": "REBARTOKEN spacing",
            "project_id": alpha["id"],
            "doc_type_filter": "building_code",
        },
    ).json()
    assert rebar["source_cards"][0]["page_number"] == 2
    assert "150 mm" in rebar["source_cards"][0]["quote"]

    specs_only = api.post(
        "/api/search",
        json={
            "query": "SPECWIDTHTOKEN",
            "project_id": alpha["id"],
            "doc_type_filter": "specification",
        },
    ).json()
    assert {card["doc_name"] for card in specs_only["source_cards"]} == {
        "alpha_spec.pdf"
    }

    closed_hit = api.post(
        "/api/search",
        json={
            "query": "CLOSEDTOKEN",
            "project_id": alpha["id"],
            "doc_type_filter": "inspection_report",
        },
    ).json()
    assert closed_hit["has_deficiency"] is False
    assert closed_hit["deficiency_text"] is None
    assert closed_hit["source_cards"][0]["finding_status"] == "closed"
    assert "DEFICIENCY DETECTED" not in closed_hit["ai_summary"]

    unverified_hit = api.post(
        "/api/search",
        json={
            "query": "UNVERIFIEDTOKEN",
            "project_id": alpha["id"],
            "doc_type_filter": "inspection_report",
        },
    ).json()
    assert unverified_hit["has_deficiency"] is False
    assert unverified_hit["deficiency_status"] == "requires_verification"
    assert unverified_hit["deficiency_text"].startswith("REQUIRES VERIFICATION")

    hidden = api.post(
        "/api/search",
        json={
            "query": "BETAONLYTOKEN",
            "project_id": alpha["id"],
            "doc_type_filter": "All",
        },
    )
    assert hidden.status_code == 200
    hidden_body = hidden.json()
    assert hidden_body["ai_summary"] == NO_EVIDENCE
    assert hidden_body["source_cards"] == []
    assert "BETAONLYTOKEN" not in json.dumps(hidden_body)
    assert "complies" not in hidden_body["ai_summary"].lower()

    visible_to_beta = api.post(
        "/api/search",
        json={
            "query": "BETAONLYTOKEN",
            "project_id": beta["id"],
            "doc_type_filter": "All",
        },
    ).json()
    assert visible_to_beta["source_cards"][0]["doc_name"] == "beta_secret.pdf"

    global_from_beta = api.post(
        "/api/search",
        json={
            "query": "REBARTOKEN",
            "project_id": beta["id"],
            "doc_type_filter": "building_code",
        },
    ).json()
    assert global_from_beta["source_cards"][0]["doc_name"] == "fire_code.pdf"

    alpha_spec_hidden = api.post(
        "/api/search",
        json={
            "query": "SPECWIDTHTOKEN",
            "project_id": beta["id"],
            "doc_type_filter": "All",
        },
    ).json()
    assert alpha_spec_hidden["ai_summary"] == NO_EVIDENCE

    unknown = api.post(
        "/api/search",
        json={"query": "completely unrelated pottery", "project_id": alpha["id"]},
    )
    assert unknown.status_code == 200
    assert unknown.json()["ai_summary"] == NO_EVIDENCE

    missing_project = api.post(
        "/api/search", json={"query": "EXITWIDTHTOKEN", "project_id": "proj-missing"}
    )
    assert missing_project.status_code == 404

    bad_filter = api.post(
        "/api/search",
        json={
            "query": "EXITWIDTHTOKEN",
            "project_id": alpha["id"],
            "doc_type_filter": "novel",
        },
    )
    assert bad_filter.status_code == 400

    empty_query = api.post(
        "/api/search", json={"query": "   ", "project_id": alpha["id"]}
    )
    assert empty_query.status_code == 400


def test_project_pdf_is_not_readable_from_another_project(api):
    alpha = create_project(api, "Alpha")
    beta = create_project(api, "Beta")
    uploaded = upload(
        api,
        "alpha_only.pdf",
        ["Section 1.1 Private\nSPECWIDTHTOKEN private project text."],
        project_id=alpha["id"],
        scope="project",
        doc_type="specification",
    )
    doc_id = uploaded.json()["doc_id"]
    assert api.get(f"/api/documents/{doc_id}/file").status_code == 404
    assert (
        api.get(
            f"/api/documents/{doc_id}/file", params={"project_id": beta["id"]}
        ).status_code
        == 404
    )
    allowed = api.get(
        f"/api/documents/{doc_id}/file", params={"project_id": alpha["id"]}
    )
    assert allowed.status_code == 200
    assert allowed.content.startswith(b"%PDF")
    assert api.get("/api/documents/doc_zzzzzzzz/file").status_code == 404
    assert api.get("/api/documents/doc_abcd1234/file").status_code == 404
    removed = api.delete(f"/api/documents/{doc_id}", params={"project_id": beta["id"]})
    assert removed.status_code == 404
    assert (
        api.delete(
            f"/api/documents/{doc_id}", params={"project_id": alpha["id"]}
        ).status_code
        == 200
    )
    assert (
        api.get(
            f"/api/documents/{doc_id}/file", params={"project_id": alpha["id"]}
        ).status_code
        == 404
    )


def test_env_example_has_no_live_credentials():
    from pathlib import Path

    text = (
        Path(__file__)
        .resolve()
        .parent.parent.joinpath(".env.example")
        .read_text(encoding="utf-8")
    )
    assert "GROQ_API_KEY=" in text
    assert "MONGODB_URI=" in text
    assert "gsk_" not in text
    assert "mongodb+srv://" not in text or "<" in text
