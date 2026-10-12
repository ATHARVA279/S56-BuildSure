from types import SimpleNamespace

from src.rag import NO_EVIDENCE, citations_are_grounded, generate_compliance_answer


CHUNK = {
    "file_name": "code.pdf",
    "source": "code.pdf",
    "section": "Section 7.2 Exit Width",
    "section_id": "7.2",
    "page_number": 2,
    "scope": "global",
    "doc_type": "building_code",
    "quote": "The clear width shall be at least 1.0 m.",
    "text": "The clear width shall be at least 1.0 m.",
}


class FakeCompletions:
    def __init__(self, replies):
        self.replies = list(replies)

    def create(self, **kwargs):
        content = self.replies.pop(0)
        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def fake_client(replies):
    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(replies)))


def test_no_chunks_returns_the_required_message():
    result = generate_compliance_answer("How wide is the exit?", [])
    assert result["answer"] == NO_EVIDENCE
    assert result["citations"] == []


def test_invalid_citation_is_not_shown_as_verified(monkeypatch):
    monkeypatch.setattr("src.rag.get_groq_client", lambda: None)
    bad = "The corridor must be 2.5 m wide [Other.pdf, 9.9, Page 99]."
    good = "The clear width shall be at least 1.0 m [code.pdf, 7.2, Page 2]."
    result = generate_compliance_answer(
        "What is the exit width?",
        [CHUNK],
        client=fake_client([bad, good]),
    )
    assert "Other.pdf" not in result["answer"]
    assert "code.pdf, 7.2, Page 2" in result["answer"]
    assert citations_are_grounded(result["answer"], [CHUNK])


def test_ungrounded_model_text_falls_back_to_retrieved_quote():
    bad = "The corridor must be 2.5 m wide [Other.pdf, 9.9, Page 99]."
    result = generate_compliance_answer(
        "What is the exit width?",
        [CHUNK],
        client=fake_client([bad, bad]),
    )
    assert "Other.pdf" not in result["answer"]
    assert "1.0 m" in result["answer"]
    assert "code.pdf, 7.2, Page 2" in result["answer"]
    assert result["generation_mode"] == "extractive_after_citation_check"


def test_missing_api_key_quotes_the_source(monkeypatch):
    monkeypatch.setattr("src.rag.get_groq_client", lambda: None)
    result = generate_compliance_answer("What is the exit width?", [CHUNK])
    assert result["generation_mode"] == "extractive"
    assert "GROQ_API_KEY" in result["answer"]
    assert "1.0 m" in result["answer"]
    assert "complies" not in result["answer"].lower()
