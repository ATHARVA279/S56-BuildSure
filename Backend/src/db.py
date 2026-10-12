"""MongoDB Atlas database connection and vector search index management."""
import logging
from typing import Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from src.config import (
    CHUNKS_COLLECTION,
    DATABASE_NAME,
    DOCUMENTS_COLLECTION,
    EMBEDDING_DIM,
    MONGODB_URI,
    PROJECTS_COLLECTION,
    SIMILARITY_METRIC,
    VECTOR_INDEX_NAME,
)

logger = logging.getLogger(__name__)

# Global singleton client
_mongo_client: Optional[MongoClient] = None

# MongoDB Atlas Vector Search index definition
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
            {
                "type": "filter",
                "path": "project_id",
            },
            {
                "type": "filter",
                "path": "scope",
            },
            {
                "type": "filter",
                "path": "doc_type",
            },
        ]
    },
}


def get_mongo_client(uri: Optional[str] = None) -> MongoClient:
    """Return a cached PyMongo client instance."""
    global _mongo_client
    if _mongo_client is None:
        target_uri = uri or MONGODB_URI
        logger.info("Initializing MongoDB client...")
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


def get_documents_collection(db: Optional[Database] = None) -> Collection:
    """Return the documents metadata collection."""
    target_db = db if db is not None else get_db()
    return target_db[DOCUMENTS_COLLECTION]


def get_chunks_collection(db: Optional[Database] = None) -> Collection:
    """Return the vector chunks collection."""
    target_db = db if db is not None else get_db()
    return target_db[CHUNKS_COLLECTION]


def get_projects_collection(db: Optional[Database] = None) -> Collection:
    """Return the projects collection."""
    target_db = db if db is not None else get_db()
    return target_db[PROJECTS_COLLECTION]


def ping_db() -> bool:
    """Check connectivity to the MongoDB instance."""
    try:
        client = get_mongo_client()
        client.admin.command("ping")
        return True
    except Exception as exc:
        logger.warning(f"MongoDB ping failed: {exc}")
        return False


def create_vector_search_index(chunks_collection: Optional[Collection] = None) -> dict:
    """Create or verify the Atlas Vector Search index on the vector_chunks collection.

    Note: MongoDB Atlas Vector Search indexes can be created via PyMongo 4.7+
    using `SearchIndexModel` or directly in the MongoDB Atlas Web Console.
    """
    col = chunks_collection if chunks_collection is not None else get_chunks_collection()
    try:
        from pymongo.operations import SearchIndexModel

        index_model = SearchIndexModel(
            definition=ATLAS_VECTOR_INDEX_DEFINITION["definition"],
            name=VECTOR_INDEX_NAME,
            type="vectorSearch",
        )
        result = col.create_search_index(model=index_model)
        logger.info(f"MongoDB Atlas vector index creation triggered: {result}")
        return {"status": "created", "name": result, "spec": ATLAS_VECTOR_INDEX_DEFINITION}
    except Exception as exc:
        logger.info(
            f"Note on Atlas Search Index creation (may already exist or requires Atlas console): {exc}"
        )
        return {"status": "manual_or_existing", "error": str(exc), "spec": ATLAS_VECTOR_INDEX_DEFINITION}


def init_db():
    """Ensure standard database indexes on metadata fields for fast queries."""
    try:
        docs_col = get_documents_collection()
        chunks_col = get_chunks_collection()
        projects_col = get_projects_collection()

        # Unique or filter indexes
        docs_col.create_index("doc_id", unique=True, sparse=True)
        docs_col.create_index([("project_id", 1), ("scope", 1)])

        chunks_col.create_index([("project_id", 1), ("scope", 1), ("doc_type", 1)])
        chunks_col.create_index("doc_id")

        projects_col.create_index("id", unique=True, sparse=True)

        # Attempt to create Atlas Vector Index if supported
        create_vector_search_index(chunks_col)
    except Exception as exc:
        logger.warning(f"Could not initialize database indexes: {exc}")
