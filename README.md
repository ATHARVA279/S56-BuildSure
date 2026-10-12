# BuildSure

BuildSure is a compliance assistant for construction site engineers. An engineer selects a project, asks a question in plain language, and gets an answer drawn only from the documents that apply to that job: shared building codes, that project's specifications, and that project's inspection reports. Each material statement cites the file, section, and page. The original PDF opens on that page.

If the library does not support an answer, BuildSure says:

`No relevant compliance rule found in current repository.`

The sample documents in `Backend/data/sample_docs` are fictional. They are not real regulations.

## What you can do

- Create a project and select it as the active workspace.
- Upload a PDF as a building code, a specification, or an inspection report.
- Keep building codes global, so every project can use them.
- Keep specifications and inspection reports inside one project. Other projects cannot retrieve them.
- Ask a compliance question and read the answer with source cards.
- See **DEFICIENCY DETECTED** when a retrieved inspection report marks a finding as open.
- Open the cited PDF and check the passage.

A missing finding is not treated as proof that the work complies. A finding marked closed is not shown as an active deficiency. A finding with no status is labeled as requiring verification.

## Architecture

```text
PDF upload
  -> page text and section labels
  -> chunks with page, section, and project metadata
  -> local embedding
  -> MongoDB Atlas (vector_chunks)
  -> filtered vector search
  -> Groq, using only those passages
  -> answer, citations, and the original PDF
```

| Part | Where | Role |
|---|---|---|
| Website | `Frontend/` | React and Vite. Project selection, search, source cards, and the PDF pane. |
| API | `Backend/src/main.py` | FastAPI. Projects, upload, search, and file download. |
| Ingestion | `Backend/src/ingestion.py` | Validates the PDF, extracts text, chunks it, embeds it, and stores it. |
| Embeddings | `Backend/src/embedder.py` | `all-MiniLM-L6-v2`, 384 dimensions, run locally. |
| Database | MongoDB Atlas | `construct_code_db`. Collections: `projects`, `documents`, `vector_chunks`. |
| Answers | `Backend/src/rag.py` | Groq model `openai/gpt-oss-20b`. Citations must match a retrieved chunk. |

Search returns a chunk only when it is a global document, or a project document for the active project, and it matches the selected document type.

## Prerequisites

- Python 3.11
- Node.js 18 or newer
- A MongoDB Atlas cluster
- A Groq API key, if you want written answers rather than quoted passages

## Setup

From `Backend`:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put the real values in `Backend/.env`. Do not commit that file.

| Variable | Purpose |
|---|---|
| `MONGODB_URI` | Atlas connection string |
| `MONGODB_DB_NAME` | Database name. Default `construct_code_db` |
| `BUILDSURE_STORAGE` | `mongo` for Atlas. `local` stores JSON files on the machine if you are working without a cluster |
| `GROQ_API_KEY` | Groq key. Leave empty to quote retrieved text only |
| `GROQ_MODEL` | Optional. Default `openai/gpt-oss-20b` |
| `CORS_ORIGINS` | Frontend origin. Default `http://localhost:5173,http://127.0.0.1:5173` |
| `MAX_UPLOAD_BYTES` | Upload limit. Default 25 MB |

From `Frontend`:

```bash
npm install
```

Leave `VITE_API_BASE_URL` empty in local development. The Vite server proxies `/api` to the API. For a deployed site, set it to the public API origin before `npm run build`.

## Atlas vector index

On the `vector_chunks` collection, create a vector search index named `vector_index`:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    },
    { "type": "filter", "path": "project_id" },
    { "type": "filter", "path": "scope" },
    { "type": "filter", "path": "doc_type" }
  ]
}
```

The dimensions must stay 384. That is the size of `all-MiniLM-L6-v2`. The same definition is in `Backend/src/db.py`.

## Run

Terminal 1, from `Backend`:

```bash
source .venv/bin/activate
python scripts/seed_repository.py
uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, from `Frontend`:

```bash
npm run dev
```

Open `http://127.0.0.1:5173`.

The seed loads two workspaces:

- **Project Alpha — Commercial Tower**, Site 44. Specifications and inspection reports, plus the global codes.
- **Project Beta**, Site 12. The Block A inspection report, plus the global codes.

`python scripts/seed_repository.py --force` deletes the previously seeded documents and indexes them again. Do not use it on a database that already holds real uploads.

`GET http://127.0.0.1:8000/api/health` should report `storage` as `mongo`, `database_connected` as `true`, and `llm_configured` as `true` when the Groq key is set.

## How a document becomes an answer

1. The upload must be a PDF. A global file is stored with `project_id` set to `global`. A project file must name an existing project.
2. Text is extracted one page at a time. Page numbers stay the PDF's own numbers. A PDF with no text is rejected. OCR is not implemented.
3. Headings such as `Section 7.2`, `Clause CW-3`, and `Finding B-1` start a new section. Text before the next heading stays with the current section, including when it continues onto the next page.
4. Long sections are split at about 400 words, with about 50 words of overlap.
5. Each chunk is embedded and stored with its file name, scope, document type, section, and page.
6. A question is embedded with the same model. Atlas searches `vector_chunks` after applying the project and document-type filter. Scores below 0.35 are dropped.
7. Groq writes the answer from those passages. An open inspection finding in the retrieved text is returned as a deficiency. The website can open the stored PDF on the cited page.

Uploaded PDF bytes are kept on the API machine under `Backend/data/uploads/`. The database stores the text, the vectors, and the metadata.

## Tests

From `Backend`:

```bash
source .venv/bin/activate
pytest
```

These tests use an in-memory store. They do not call Atlas or Groq.

From `Frontend`:

```bash
npm run typecheck
npm run lint
npm run build
```

## Limits

- There are no user accounts. Isolation is by project id.
- Scanned PDFs cannot be read.
- Without `GROQ_API_KEY`, the API returns quoted passages and says the model is not configured.
- A broad search can surface an open inspection finding that is only moderately related to the question. The quote is from that file. The answer does not invent a compliance decision.
