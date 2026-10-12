"""Checks the answer key itself: every expected clause must exist in the documents."""
import json
from pathlib import Path

from src.chunker import chunk_documents
from src.loader import load_documents

QUESTIONS_FILE = Path(__file__).resolve().parent / "eval_questions.json"


def load_questions():
    return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))


def known_clauses():
    return {(c["source"], c["section_id"]) for c in chunk_documents(load_documents())}


def targets(q):
    """All (source, section_id) pairs that count as a correct hit for a question."""
    pairs = [(q["expected"]["source"], q["expected"]["section_id"])]
    pairs += [(a["source"], a["section_id"]) for a in q.get("also_ok", [])]
    return pairs


def test_has_at_least_15_questions():
    assert len(load_questions()) >= 15


def test_ids_are_unique_and_questions_non_empty():
    qs = load_questions()
    assert len({q["id"] for q in qs}) == len(qs)
    assert all(q["question"].strip().endswith("?") for q in qs)


def test_every_expected_clause_exists_in_the_documents():
    clauses = known_clauses()
    for q in load_questions():
        for pair in targets(q):
            assert pair in clauses, f"{q['id']}: {pair} not found in documents"


def test_questions_cover_all_three_document_types():
    types = {s.split("_")[0] for q in load_questions() for s, _ in targets(q)}
    assert {"building", "spec", "inspection"} <= types
