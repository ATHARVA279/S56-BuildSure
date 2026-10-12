# BuildSure

BuildSure is a compliance assistant for construction site engineers. An engineer picks a project, works with building codes, specifications, and inspection reports, and asks a plain-language question. The answer is limited to retrieved text from the global code library and that project's documents, with the file, section, and page cited. If the library does not support an answer, the response is:

`No relevant compliance rule found in current repository.`

Sample documents in `Backend/data/sample_docs` are fictional. They are not real regulations.

## Architecture

- **Frontend** (`Frontend/`): React 18 and Vite. Project selection, search, source cards, deficiency warnings, and a PDF pane.
- **API** (`Backend/src/main.py`): FastAPI. Projects, PDF upload, search, and file serving.
- **Ingestion** (`loader.py`, `chunker.py`, `ingestion.py`): pypdf, one-based pages, section headings, about 400 words per chunk with about 50 words of overlap on long clauses.
- **Embeddings** (`embedder.py`): `sentence-transformers` model `all-MiniLM-L6-v2`, 384 dimensions, local, no API key.
- **Store**: MongoDB when `MONGODB_URI` is reachable. Otherwise JSON files in `Backend/data/local_db/` (`BUILDSURE_STORAGE=local` or `auto`). Atlas Vector Search is used when the cluster index exists; otherwise the same metadata filter is applied and rows are ranked by cosine similarity.
- **Answers** (`rag.py`): Groq model `llama-3.1-8b-instant` when `GROQ_API_KEY` is set. Citations that do not match a retrieved chunk are dropped. With no key, the API quotes the retrieved text and says the model is not configured.

Collections: `projects`, `documents`, `vector_chunks`.

A search only returns chunks where `scope` is `global`, or `scope` is `project` and `project_id` is the active project, and the document type matches the filter.

## Prerequisites

- Python 3.11 (3.14 was not used for this app)
- Node.js 18 or newer
- Optional: MongoDB Atlas, or a local MongoDB, and a Groq API key

## Install

```bash
cd Backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

```bash
cd Frontend
npm install
```

## Environment

Copy `Backend/.env.example` to `Backend/.env`. Do not commit real keys.

| Variable | Role |
|---|---|
| `MONGODB_URI` | Atlas or local MongoDB connection string |
| `MONGODB_DB_NAME` | Database name, default `construct_code_db` |
| `BUILDSURE_STORAGE` | `auto` (default), `mongo`, `local`, or `memory` |
| `GROQ_API_KEY` | Optional. Empty means quotes only |
| `CORS_ORIGINS` | Default `http://localhost:5173,http://127.0.0.1:5173` |
| `MAX_UPLOAD_BYTES` | Default 25 MB |

`Frontend/.env.example` sets `VITE_API_BASE_URL` empty so the dev server proxies `/api`.

## Run

Terminal 1, API:

```bash
cd Backend
source .venv/bin/activate
python scripts/seed_repository.py
uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, UI:

```bash
cd Frontend
npm run dev
```

Open `http://127.0.0.1:5173`. The seed creates **Project Alpha — Commercial Tower** (Site 44) and **Project Beta** (Site 12). Building codes are global. Specs and inspections are on Alpha, except the Block A inspection, which is on Beta.

`python scripts/seed_repository.py --force` deletes previously seeded documents and PDFs, then indexes again. Do not point `--force` at a database you need to keep.

## Tests

```bash
cd Backend
source .venv/bin/activate
pytest
```

```bash
cd Frontend
npm run typecheck
npm run lint
npm run build
```

Pytest uses an in-memory store and does not call MongoDB, Atlas, or Groq. Latest run: 65 passed. Details are in `docs/TEST_REPORT.md`.

## MongoDB Atlas vector index

On the `vector_chunks` collection, create a vector search index named `vector_index`. The definition is in `docs/atlas_vector_index.json` and in `ATLAS_VECTOR_INDEX_DEFINITION` in `Backend/src/db.py`:

- vector path `embedding`, 384 dimensions, cosine
- filter fields `project_id`, `scope`, `doc_type`

Set `BUILDSURE_STORAGE=mongo` and a real `MONGODB_URI`. If `$vectorSearch` is unavailable, the API logs that and ranks the filtered rows in process. That fallback is what a local JSON store and a non-Atlas MongoDB server use. This workspace did not connect to Atlas.

## How ingestion and retrieval work

1. Upload is PDF-only. Global uploads are stored as `project_id=global` even if another id is sent. Project uploads must name an existing project.
2. Text is extracted per page. A page with no text is skipped and does not renumber later pages. A PDF with no text at all returns HTTP 422 and says OCR is not implemented.
3. Headings such as `Section 7.2`, `Clause CW-3`, `Finding B-1`, and `1005.1 Title` start a section. A later page can continue the previous section. A sentence that only mentions "Section 4.2 of the code" stays in the current finding.
4. Each chunk stores the file, scope, type, section, one-based page, quote, and embedding.
5. Search embeds the question with the same model, applies the scope and type filter, and drops scores under 0.35 (`SIMILARITY_THRESHOLD`).
6. Open inspection findings in the retrieved text produce `DEFICIENCY DETECTED`. Closed findings do not. A problem statement with no status is labeled as requiring verification. Absence of a finding is not treated as compliance.

## Known limitations

- No Groq key: answers are quotations, not a written ruling. The UI says so.
- No Atlas cluster in this environment: vector search is the cosine fallback.
- Scanned PDFs are rejected. OCR is not implemented.
- An "All" search can include an open inspection finding whose embedding is only moderately close to the question. The quote is from that file; the summary does not invent a compliance decision.
- `Backend/scripts/ingest.py` is the older Chroma path. The API does not read `chroma_db/`.
- There is no user login. Project file access is enforced by project id, not by an account.

## More detail

- [Audit](docs/AUDIT_REPORT.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Test report](docs/TEST_REPORT.md)
- [Product requirements](Backend/docs/PRD.md)
- [Original system design](Backend/docs/SYSTEM_DESIGN.md)
