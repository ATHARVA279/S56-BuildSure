# BuildSure implementation plan

Statuses below are after the work in this tree. A task is complete only where the acceptance check was actually run.

## P0 — Startup and the core loop

| Task | Status | Where | What was wrong | Change | Acceptance check |
|---|---|---|---|---|---|
| Backend imports and boot | Complete | `Backend/src/main.py` | Not run before this work | Boot against the selected store | Uvicorn startup log and `GET /api/health` |
| Retriever tests vs Mongo API | Complete | `Backend/src/retriever.py`, `Backend/tests/test_retriever.py` | Five tests called a Chroma fake | Tests use `MemoryCollection`; filter requires project scope | `pytest` retriever tests |
| Frontend calls the API | Complete | `Frontend/src/api.ts`, `Frontend/src/App.tsx` | Search used `mockData.ts` | Live project, search, and document calls | Browser search on Project Alpha |
| Dev proxy | Complete | `Frontend/vite.config.ts` | No API proxy | `/api` proxies to `127.0.0.1:8000` | `GET http://127.0.0.1:5173/api/health` returned 200 |

## P1 — Documents, retrieval, answers

| Task | Status | Where | What was wrong | Change | Acceptance check |
|---|---|---|---|---|---|
| Project API | Complete | `POST /api/projects` | Accepted `name` only and reused a workspace by display name | Accepts `project_name` or `name`, returns id and `created_at`, always creates a new id unless that id already exists | `test_create_project_returns_id_and_timestamp` |
| PDF upload rules | Complete | `Backend/src/ingestion.py` | Text files were accepted; global files kept a foreign project id; status could look indexed after a failed embed | PDF magic and extension, size limit, project check, status `indexed` only after chunks and the file are stored | `test_upload_validation_and_failed_records_are_not_indexed` |
| Page and section provenance | Complete | `Backend/src/loader.py`, `Backend/src/chunker.py` | A wrapped "Section 4.2 of the code" line became its own heading | One-based pages kept; continuation text keeps the previous section; lowercase inline references stay in the body | Chunker and loader tests; live quote for Finding B-1 includes the following sentence |
| Embeddings | Complete locally | `Backend/src/embedder.py` | Dimension was configured but not checked on upload | Reject vectors whose length is not 384 | API dimension test; live model `all-MiniLM-L6-v2` |
| Mongo / Atlas index | Unverified | `Backend/src/db.py`, `docs/atlas_vector_index.json` | Index spec existed; no cluster | Spec kept at 384 cosine with `project_id`, `scope`, `doc_type` filters | Unit test of the spec. Live Atlas still needs a cluster |
| Local store when Mongo is down | Complete | `Backend/src/local_store.py` | Requests failed closed when Mongo was absent | JSON collections implement the same filter and fall back to cosine ranking | Seed of 17 PDFs and live search |
| Scope filter | Complete | `build_search_filter` | `project_id` match did not also require `scope=project` | Global rows, or project rows for the active id, then the type filter | Isolation tests and Block A vs Alpha |
| Grounded generation | Partial | `Backend/src/rag.py` | No-evidence text differed; bad citations could be shown | Required sentence when nothing qualifies; citations must match a chunk; one retry; otherwise quote the chunks | `tests/test_grounding.py`. Groq itself was not called |
| Deficiencies | Complete | `Backend/src/deficiencies.py` | No status parsing; UI banner was fixed text | Open status warns; closed does not; missing status asks for verification | Deficiency tests and the browser banner |
| Source PDF | Complete | `GET /api/documents/{doc_id}/file` | Bytes were discarded after parse | Files saved as `doc_<8 hex>.pdf`; project files need the owning id | API access tests; browser iframe; response started with `%PDF` |

## P2 — UI states

| Task | Status | Notes |
|---|---|---|
| Project selector and create dialog | Complete | Create posts `project_name`. Errors stay in the dialog. |
| Document library | Complete | Lists global plus the active project. Scope and type are sent with upload. Delete calls the API. |
| Results, citations, deficiency | Complete | Hard-coded Finding 7 banner removed. Banner uses `has_deficiency` and `deficiency_status`. |
| PDF pane | Complete | Iframe of the served file. Next page stops at `page_count`. No fake highlight layer. |
| Empty and error copy | Partial | Loading was seen in the browser. The exact no-evidence sentence was confirmed with `POST /api/search`, not a second browser query. |

## P3 — Tests

| Task | Status | Check |
|---|---|---|
| API, retrieval, chunk, citation, and deficiency tests | Complete | `pytest`: 65 passed |
| Frontend typecheck, lint, build | Complete | All three scripts passed |
| Live MiniLM seed and search | Complete | `scripts/seed_repository.py`; corridor question cited Section 7.2 |
| Atlas and Groq integration tests | Not done | No credentials |

## P4 — Not in this change

- Accounts and roles. The PRD leaves them out of scope.
- OCR for scanned PDFs. Empty text returns a clear 422.
- A separate compliance-report page. The search answer is the assessment.
- Mobile viewport pass.
- Replacing the legacy Chroma `scripts/ingest.py` path. It still works with an injected collection. `chromadb` is not installed.

## Known limitation

An "All" search keeps chunks at or above similarity 0.35 and also merges inspection hits above that line. On the corridor question, Finding B-1 (rebar, status open) appeared beside Section 7.2. The quote is from the inspection file; the summary does not say the 1.05 m corridor complies. Tightening that margin, or adding a Groq key so the model can refuse excerpts that do not answer the question, is the next quality pass.
