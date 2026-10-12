"""Central settings for BuildSure / RegFind service."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(ROOT_DIR / ".env")

# Data and storage
DOCS_DIR = ROOT_DIR / "data" / "sample_docs"
CHROMA_DIR = ROOT_DIR / "chroma_db"
COLLECTION_NAME = "regfind_chunks"

# MongoDB Atlas
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGODB_DB_NAME", "construct_code_db")
DOCUMENTS_COLLECTION = "documents"
CHUNKS_COLLECTION = "vector_chunks"
PROJECTS_COLLECTION = "projects"
VECTOR_INDEX_NAME = "vector_index"
EMBEDDING_DIM = 384
SIMILARITY_METRIC = "cosine"

# Chunking
CHUNK_SIZE = 400      # approximate words/tokens per chunk
CHUNK_OVERLAP = 50    # approximate words/tokens shared between neighbouring chunks

# Embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Retrieval
TOP_K = 4
SIMILARITY_THRESHOLD = 0.35

# LLM (Groq). llama-3.1-8b-instant was removed from Groq's catalog.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# Uploads and local fallback store. MongoDB remains the configured database.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
UPLOAD_DIR = ROOT_DIR / "data" / "uploads"
LOCAL_DB_DIR = ROOT_DIR / "data" / "local_db"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
