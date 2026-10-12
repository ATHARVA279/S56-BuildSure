"""Central settings for RegFind. Tune these after running scripts/evaluate.py."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Data and storage
DOCS_DIR = ROOT_DIR / "data" / "sample_docs"
CHROMA_DIR = ROOT_DIR / "chroma_db"
COLLECTION_NAME = "regfind_chunks"

# Chunking
CHUNK_SIZE = 400      # approximate tokens per chunk
CHUNK_OVERLAP = 50    # approximate tokens shared between neighbouring chunks

# Embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Retrieval
TOP_K = 4
SIMILARITY_THRESHOLD = 0.35   # placeholder: tune using the evaluation set

# LLM
LLM_MODEL = "llama-3.1-8b-instant"
