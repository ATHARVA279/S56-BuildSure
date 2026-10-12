"""MongoDB connection, with a local JSON store when MongoDB is down.

`BUILDSURE_STORAGE` selects the backend:

- `mongo`: always use `MONGODB_URI`
- `local`: persist collections as JSON files under `data/local_db`
- `memory`: process-local store used by tests
- `auto` (default): MongoDB when a ping succeeds, otherwise the JSON files

Atlas Vector Search is only available on MongoDB Atlas. The index definition
below is what a cluster needs. Local MongoDB and the JSON store do not build
that index; retrieval then uses the same metadata filter and cosine ranking.
"""
import logging
import os
from typing import Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from src.config import (
    CHUNKS_COLLECTION,
    DATABASE_NAME,
    DOCUMENTS_COLLECTION,
    EMBEDDING_DIM,
    LOCAL_DB_DIR,
    MONGODB_URI,
    PROJECTS_COLLECTION,
    SIMILARITY_METRIC,
    VECTOR_INDEX_NAME,
)
from src.local_store import LocalJsonCollection, MemoryCollection

logger = logging.getLogger(__name__)

_mongo_client: Optional[MongoClient] = None
_local_collections: dict[str, MemoryCollection] = {}
_auto_kind: Optional[str] = None

ATLAS_VECTOR_INDEX_DEFINITION = {
    "name": VECTOR_INDEX_NAME,
    "type": "vectorSearch",
    "definition": {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": EMBEDDING_DIM,
                "similarity": SIMILARITY_METRIC,
            },
            {"type": "filter", "path": "project_id"},
            {"type": "filter", "path": "scope"},
            {"type": "filter", "path": "doc_type"},
        ]
    },
}


def storage_kind() -> str:
    """Return mongo, local, or memory. `auto` is resolved once per process."""
    global _auto_kind
    mode = os.getenv("BUILDSURE_STORAGE", "auto").strip().lower()
    if mode in {"memory", "local", "mongo"}:
        return mode
    if _auto_kind:
        return _auto_kind
    _auto_kind = "mongo" if _ping_uri(MONGODB_URI) else "local"
    if _auto_kind == "local":
        logger.warning(
            "MongoDB is not reachable. Using the local JSON document store. "
            "Atlas Vector Search is not active."
        )
    return _auto_kind


def reset_storage() -> None:
    """Drop cached clients. Tests call this so cases do not share rows."""
    global _mongo_client, _auto_kind
    _local_collections.clear()
    _auto_kind = None
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None


def _ping_uri(uri: str) -> bool:
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=800, connectTimeoutMS=800)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


def get_mongo_client(uri: Optional[str] = None) -> MongoClient:
    """Return a cached PyMongo client instance."""
    global _mongo_client
    if _mongo_client is None:
        target_uri = uri or MONGODB_URI
        logger.info("Initializing MongoDB client")
        _mongo_client = MongoClient(
            target_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            appname="BuildSure-RegFind",
        )
    return _mongo_client


def get_db(db_name: Optional[str] = None) -> Database:
    """Return the application database instance."""
    client = get_mongo_client()
    return client[db_name or DATABASE_NAME]


def _local_collection(name: str) -> MemoryCollection:
    if name not in _local_collections:
        if storage_kind() == "memory":
            _local_collections[name] = MemoryCollection()
        else:
            LOCAL_DB_DIR.mkdir(parents=True, exist_ok=True)
            _local_collections[name] = LocalJsonCollection(LOCAL_DB_DIR / f"{name}.json")
    return _local_collections[name]


def get_documents_collection(db: Optional[Database] = None):
    """Return the documents metadata collection."""
    if storage_kind() != "mongo":
        return _local_collection(DOCUMENTS_COLLECTION)
    target_db = db if db is not None else get_db()
    return target_db[DOCUMENTS_COLLECTION]


def get_chunks_collection(db: Optional[Database] = None):
    """Return the vector chunks collection."""
    if storage_kind() != "mongo":
        return _local_collection(CHUNKS_COLLECTION)
    target_db = db if db is not None else get_db()
    return target_db[CHUNKS_COLLECTION]


def get_projects_collection(db: Optional[Database] = None):
    """Return the projects collection."""
    if storage_kind() != "mongo":
        return _local_collection(PROJECTS_COLLECTION)
    target_db = db if db is not None else get_db()
    return target_db[PROJECTS_COLLECTION]


def ping_db() -> bool:
    """Check that the selected store can be used."""
    kind = storage_kind()
    if kind in {"memory", "local"}:
        return True
    try:
        get_mongo_client().admin.command("ping")
        return True
    except Exception as exc:
        logger.warning("MongoDB ping failed: %s", type(exc).__name__)
        return False


def create_vector_search_index(chunks_collection: Optional[Collection] = None) -> dict:
    """Create or verify the Atlas Vector Search index on vector_chunks.

    Local MongoDB and the JSON store cannot build this index. The returned
    spec is the definition to create in the Atlas UI or with PyMongo on Atlas.
    """
    if storage_kind() != "mongo":
        return {
            "status": "not_atlas",
            "spec": ATLAS_VECTOR_INDEX_DEFINITION,
        }
    col = chunks_collection if chunks_collection is not None else get_chunks_collection()
    try:
        from pymongo.operations import SearchIndexModel

        index_model = SearchIndexModel(
            definition=ATLAS_VECTOR_INDEX_DEFINITION["definition"],
            name=VECTOR_INDEX_NAME,
            type="vectorSearch",
        )
        result = col.create_search_index(model=index_model)
        logger.info("MongoDB Atlas vector index creation triggered")
        return {"status": "created", "name": result, "spec": ATLAS_VECTOR_INDEX_DEFINITION}
    except Exception as exc:
        logger.info("Atlas Search index was not created from this process: %s", type(exc).__name__)
        return {
            "status": "manual_or_existing",
            "error_type": type(exc).__name__,
            "spec": ATLAS_VECTOR_INDEX_DEFINITION,
        }


def init_db():
    """Ensure metadata indexes. Atlas index creation is best-effort."""
    kind = storage_kind()
    logger.info("Document store: %s", kind)
    if kind != "mongo":
        get_documents_collection()
        get_chunks_collection()
        get_projects_collection()
        return
    try:
        docs_col = get_documents_collection()
        chunks_col = get_chunks_collection()
        projects_col = get_projects_collection()

        docs_col.create_index("doc_id", unique=True, sparse=True)
        docs_col.create_index([("project_id", 1), ("scope", 1)])

        chunks_col.create_index([("project_id", 1), ("scope", 1), ("doc_type", 1)])
        chunks_col.create_index("doc_id")

        projects_col.create_index("id", unique=True, sparse=True)
        create_vector_search_index(chunks_col)
    except Exception as exc:
        logger.warning("Could not initialize database indexes: %s", type(exc).__name__)
