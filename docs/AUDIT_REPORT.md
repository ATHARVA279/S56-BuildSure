# BuildSure audit

Audit date: 12 October 2026. Repository: `S56-BuildSure` on `main` at `bc911a5` (clean before this work). No Granola meeting notes for BuildSure were available.

The README and system design still described a ChromaDB and Streamlit pipeline. The code on `main` had already moved retrieval to MongoDB Atlas and the UI to a Vite/React app that did not call the API. This report records that baseline, then the status after the changes in this working tree.

## Baseline before changes

Commands, from the repository, with a new Python 3.11 virtualenv and `npm install`:

- `Backend/.venv/bin/python -m pytest -q` — **34 passed, 5 failed**. All five failures were in `tests/test_retriever.py`. The tests still used a Chroma-style fake (`collection.query`), while `src/retriever.py` called `count_documents`.
- `Frontend`: `npm run typecheck`, `npm run lint`, and `npm run build` — **passed**.

What was already in the tree:

- Page-aware PDF loading with pypdf (`Backend/src/loader.py`).
- Clause chunking at about 400 words with 50-word overlap for long clauses (`Backend/src/chunker.py`, `Backend/src/config.py`).
- Local MiniLM embeddings, 384 dimensions (`Backend/src/embedder.py`).
- FastAPI routes for projects, upload, and search (`Backend/src/main.py`), writing to Mongo collections `projects`, `documents`, and `vector_chunks`.
- An Atlas vector-index definition with filter paths `project_id`, `scope`, and `doc_type` (`Backend/src/db.py`).
- A React field UI (`Frontend/src`) whose search, citations, deficiency banner, and PDF pane were hard-coded in `Frontend/src/data/mockData.ts`.
- Older Chroma helpers and sample-document tests (`Backend/src/vector_store.py`, `Backend/scripts/ingest.py`, `Backend/tests`).

What was not working or not connected:

- The React app never called the API.
- Upload did not require a PDF, did not check that a project existed, could store a global file under another project's id, and marked a document stored before embedding succeeded.
- There was no saved original PDF and no file route.
- The no-evidence sentence did not match the required wording.
- Citations were not checked against retrieved chunks.
- Inspection status was not classified, and the UI always showed a hard-coded deficiency.
- Retrieval tests did not match the Mongo filter. The filter also matched any row with the active `project_id`, including rows that were not project-scoped.
- `chromadb` is not in `requirements.txt`. `scripts/ingest.py` remains the older Chroma path and is only exercised with a fake collection.

## Feature matrix

| # | Feature | Baseline | Now | Evidence |
|---|---|---|---|---|
| 1 | Frontend startup and build | COMPLETE | COMPLETE | Vite dev server on port 5173. `npm run typecheck`, `lint`, and `build` passed before and after the UI wiring. |
| 2 | Backend startup and imports | UNVERIFIED | COMPLETE | `uvicorn src.main:app` reached `Application startup complete`. `GET /api/health` returned 200. |
| 3 | Project create, list, select | PARTIAL | COMPLETE | `POST /api/projects` and `GET /api/projects` covered by `tests/test_api.py`. The browser project menu listed Project Alpha and Project Beta from the API. |
| 4 | Global document repository | PARTIAL | COMPLETE | Seeded building codes are `scope=global`. They are listed for every workspace and returned in search. |
| 5 | Project-specific documents | PARTIAL | COMPLETE | Alpha's library in the browser showed its specs and inspections and did not show Block A. Block A is stored on Beta. API isolation tests passed. |
| 6 | PDF upload and validation | PARTIAL | COMPLETE | `tests/test_api.py` rejects non-PDFs, empty files, malformed PDFs, scanned PDFs with no text, unknown types, missing projects, oversize files, and wrong embedding dimensions. Failed rows stay unindexed. The drawer is wired; a file-picker upload was not clicked in the browser. |
| 7 | Page-aware extraction | PARTIAL | COMPLETE | `test_pdf_pages_are_one_based`. Live viewer opened `building_code_fire_safety.pdf` on page 1. |
| 8 | Section and clause extraction | PARTIAL | COMPLETE | Sample clauses still match `tests/test_eval_questions.py`. Inline mentions such as "Section 4.2 of the code" stay inside the finding (`test_inline_section_reference_stays_inside_the_finding`). |
| 9 | Chunk size and overlap | COMPLETE | COMPLETE | Defaults remain 400 and 50. `test_default_windows_are_about_400_words_with_50_word_overlap`. |
| 10 | Embedding dimensions | PARTIAL | COMPLETE | Model `all-MiniLM-L6-v2`, 384 dimensions. Upload rejects a vector of the wrong length. Live seed and search used that model. |
| 11 | MongoDB persistence | PARTIAL | UNVERIFIED | No Atlas credentials in this environment. The running app uses `BUILDSURE_STORAGE=local` JSON files under `Backend/data/local_db/`. The Mongo code path is unchanged in structure and was not executed against a server. |
| 12 | Atlas vector index | PARTIAL | UNVERIFIED | Definition checked by `test_vector_index_definition_matches_embedding_and_filters` and saved in `docs/atlas_vector_index.json`. No cluster was available to build the index. Search uses cosine ranking over the metadata filter. |
| 13 | Project-aware retrieval | BROKEN | COMPLETE | `test_other_project_documents_are_excluded` and the API isolation test. Live search for Block A from Alpha did not return `inspection_report_block_a.pdf`. |
| 14 | Global plus active project | PARTIAL | COMPLETE | Filter is `(scope == global) OR (scope == project AND project_id == active)`. Beta can retrieve global fire-code chunks. |
| 15 | Document-type filters | PARTIAL | COMPLETE | API tests for `All`, `building_code`, `specification`, and `inspection_report`. Unknown filters return 400. |
| 16 | Grounded answers | PARTIAL | PARTIAL | With no `GROQ_API_KEY`, answers quote retrieved text and say the model is not configured. Fake-client tests reject citations that do not match a chunk. A live Groq call was not made. |
| 17 | Citation validation | MISSING | COMPLETE | `tests/test_grounding.py`. Live citations use chunk metadata, for example `[building_code_fire_safety.pdf, 7.2, Page 1]`. |
| 18 | Source cards | MISSING in the live UI | COMPLETE | Browser results showed section, page, quote, and retrieval text from the API. Mock answers are no longer used by `App.tsx`. |
| 19 | Deficiency detection | MISSING | COMPLETE | Open, closed, and unverified cases in `tests/test_deficiencies.py` and `tests/test_api.py`. The corridor search showed `DEFICIENCY DETECTED` for Finding B-1, which the report marks `Status: open`. |
| 20 | PDF serving and page navigation | MISSING | COMPLETE | `GET /api/documents/{id}/file` returned `application/pdf` and `%PDF-1.4`. The viewer iframe used that URL with `#page=1`. Project files require the owning project id. |
| 21 | Frontend/backend integration | MISSING | COMPLETE | Browser flow: select Project Alpha, list 8 global and 8 project PDFs, submit a compliance question, render the API summary and cards, open the source PDF. |
| 22 | Loading, empty, success, error states | MISSING | PARTIAL | The browser showed `SEARCHING` and "Searching the repository...". The no-evidence sentence was returned by a live `POST /api/search` for an unrelated question. That empty state was not repeated in the browser. API tests cover 400 and 404. |
| 23 | Automated tests | BROKEN | COMPLETE | 65 passed, 1 Starlette/httpx deprecation warning. See `docs/TEST_REPORT.md`. |
| 24 | Security and environment | PARTIAL | COMPLETE | Keys come from the environment. `.env.example` has placeholders only. Upload size and type checks exist. Document ids are `doc_` plus 8 hex characters. Project PDFs are not served to another project id. CORS origins are the Vite dev origins, not `*` with credentials. |
| 25 | Responsive usability | UNVERIFIED | UNVERIFIED | Existing responsive classes were kept. A separate mobile viewport pass was not run. |
| 26 | Setup documentation | PARTIAL | COMPLETE | Root `README.md`, `Backend/.env.example`, and `Frontend/.env.example`. |

## Pre-existing failures, kept separate

The five retriever failures existed before these edits. They were updated to the Mongo-style collection the retriever already used. The older Chroma unit tests in `tests/test_vector_store.py` and `tests/test_ingest.py` still pass against injected fakes.

## Environment limits

- Python used: 3.11.16 at `~/.local/bin/python3.11`. The system `python3` is 3.14 and was not used for the app.
- MongoDB Atlas was not configured. Local JSON storage was used instead.
- `GROQ_API_KEY` was empty. Answers are extractive quotes, not model prose.
- Docker was not usable from this environment, so a local MongoDB server was not started.
