"""Small persistent stand-in for the Mongo collections.

Used when MongoDB is not reachable, and by tests (`BUILDSURE_STORAGE=memory`).
It implements the collection methods the API and retriever call. Atlas
`$vectorSearch` is intentionally unsupported so retrieval falls back to the
same pre-filter plus cosine ranking used against a local MongoDB server.
"""
import json
import threading
from pathlib import Path
from typing import Any, Optional


def matches(doc: dict, filt: Optional[dict]) -> bool:
    """Evaluate the equality / `$and` / `$or` filters this app builds."""
    if not filt:
        return True
    if "$and" in filt:
        return all(matches(doc, part) for part in filt["$and"])
    if "$or" in filt:
        return any(matches(doc, part) for part in filt["$or"])
    for key, expected in filt.items():
        if key.startswith("$"):
            raise ValueError(f"Unsupported filter operator: {key}")
        if doc.get(key) != expected:
            return False
    return True


class MemoryCollection:
    """In-memory collection with the PyMongo methods BuildSure uses."""

    def __init__(self):
        self.docs: list[dict] = []
        self._lock = threading.Lock()

    def _after_write(self) -> None:
        return None

    def find(self, filt: Optional[dict] = None, projection: Optional[dict] = None):
        filt = filt or {}
        with self._lock:
            rows = [self._project(dict(doc), projection) for doc in self.docs if matches(doc, filt)]
        return rows

    def find_one(self, filt: Optional[dict] = None) -> Optional[dict]:
        rows = self.find(filt)
        return rows[0] if rows else None

    def insert_one(self, doc: dict) -> None:
        with self._lock:
            self.docs.append(dict(doc))
        self._after_write()

    def insert_many(self, docs: list[dict]) -> None:
        with self._lock:
            self.docs.extend(dict(doc) for doc in docs)
        self._after_write()

    def update_one(self, filt: dict, update: dict, upsert: bool = False) -> None:
        fields = dict(update.get("$set") or {})
        with self._lock:
            for doc in self.docs:
                if matches(doc, filt):
                    doc.update(fields)
                    found = True
                    break
            else:
                found = False
            if not found and upsert:
                self.docs.append(fields)
        self._after_write()

    def delete_many(self, filt: dict) -> int:
        with self._lock:
            before = len(self.docs)
            self.docs = [doc for doc in self.docs if not matches(doc, filt)]
            removed = before - len(self.docs)
        self._after_write()
        return removed

    def count_documents(self, filt: Optional[dict] = None) -> int:
        return len(self.find(filt or {}))

    def create_index(self, *args, **kwargs) -> str:
        return "local"

    def create_search_index(self, model=None) -> str:
        raise RuntimeError("Atlas Vector Search is not available on the local store")

    def aggregate(self, pipeline: list[dict]) -> list[dict]:
        if pipeline and "$vectorSearch" in pipeline[0]:
            raise RuntimeError("Atlas $vectorSearch is not available on the local store")
        raise RuntimeError("Unsupported aggregation pipeline")

    @staticmethod
    def _project(doc: dict, projection: Optional[dict]) -> dict:
        if not projection:
            return doc
        if all(value == 0 for value in projection.values()):
            for key in projection:
                doc.pop(key, None)
            return doc
        included = {key: doc.get(key) for key, value in projection.items() if value}
        return included


class LocalJsonCollection(MemoryCollection):
    """Memory collection that rewrites a JSON file after each change."""

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                self.docs = loaded

    def _after_write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        with self._lock:
            payload = json.dumps(self.docs)
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.path)
