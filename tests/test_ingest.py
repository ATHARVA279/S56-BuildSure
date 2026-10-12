"""Tests run the real loader and chunker with a fake embedder and fake store."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ingest_script", ROOT / "scripts" / "ingest.py")
ingest_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest_script)


class FakeCollection:
    def __init__(self):
        self.rows = []

    def add(self, ids, documents, embeddings, metadatas):
        self.rows.extend(zip(ids, documents, metadatas, embeddings))

    def count(self):
        return len(self.rows)


def fake_embed(texts):
    return [[float(len(t)), 1.0] for t in texts]


def test_ingest_stores_every_chunk_of_the_sample_docs():
    col = FakeCollection()
    summary = ingest_script.ingest(embed_fn=fake_embed, collection=col)
    assert summary["documents"] == 8
    assert summary["chunks"] == summary["stored"] == col.count()
    assert summary["chunks"] > summary["documents"]


def test_ingest_stores_unique_ids_and_metadata():
    col = FakeCollection()
    ingest_script.ingest(embed_fn=fake_embed, collection=col)
    ids = [r[0] for r in col.rows]
    assert len(ids) == len(set(ids))
    assert all(r[2]["source"].endswith(".txt") for r in col.rows)


def test_ingest_embeds_one_vector_per_chunk():
    col = FakeCollection()
    seen = {}

    def spy_embed(texts):
        seen["n"] = len(texts)
        return fake_embed(texts)

    summary = ingest_script.ingest(embed_fn=spy_embed, collection=col)
    assert seen["n"] == summary["chunks"]


def test_empty_docs_folder_raises(tmp_path):
    try:
        ingest_script.ingest(docs_dir=tmp_path, embed_fn=fake_embed, collection=FakeCollection())
    except ValueError as err:
        assert "No .txt documents" in str(err)
        return
    raise AssertionError("expected ValueError")


def test_missing_docs_folder_raises(tmp_path):
    try:
        ingest_script.ingest(docs_dir=tmp_path / "nope", embed_fn=fake_embed, collection=FakeCollection())
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")
