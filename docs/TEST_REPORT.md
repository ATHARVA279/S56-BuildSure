# BuildSure test report

Date: 12 October 2026. Working tree on `main` (`bc911a5`) plus the uncommitted changes from this session. Python 3.11.16, Node from the machine's `npm`.

## Baseline, before these edits

```text
cd Backend && .venv/bin/python -m pytest -q --tb=line
```

Result: **34 passed, 5 failed**. Failures:

- `tests/test_retriever.py::test_retrieve_returns_best_match_first`
- `tests/test_retriever.py::test_retrieve_respects_top_k`
- `tests/test_retriever.py::test_empty_index_raises_helpful_error`
- `tests/test_retriever.py::test_question_is_stripped_before_embedding`
- `tests/test_retriever.py::test_format_results`

Each failed with `AttributeError: 'FakeCollection' object has no attribute 'count_documents'`. `test_empty_question_raises` passed because it errors before the collection call.

Frontend, same moment:

```text
cd Frontend && npm run typecheck && npm run lint && npm run build
```

Result: **passed**. Production bundle built.

## After the changes

```text
cd Backend && .venv/bin/python -m pytest -q --tb=line
```

Result: **65 passed, 1 warning** in about 0.3–0.6s.

Warning, not a failure: Starlette reports that `starlette.testclient` wants `httpx2`. Tests use the installed `httpx` TestClient. They are not skipped.

What those tests cover, with fakes (no MongoDB, no Groq, no model download):

- Project create and validation.
- PDF upload rejection and "not indexed" status after a bad embed.
- Global files stay `project_id=global`.
- Retrieval includes global and the active project, and excludes another project's file.
- `All` and each document type. An unknown filter is HTTP 400.
- The no-evidence sentence `No relevant compliance rule found in current repository.`
- Citations that name a document or page outside the retrieved chunks are not returned.
- Open findings warn. Closed findings do not. A defect with no status is `requires_verification`.
- One-based PDF pages, 400/50 chunk windows, and section continuation across a page.
- Path-shaped document ids 404. A project PDF 404s for the other project id.
- Atlas index spec: 384 dimensions, cosine path `embedding`, filters `project_id`, `scope`, `doc_type`.

Frontend again after the UI edits:

```text
cd Frontend && npm run typecheck && npm run lint && npm run build
```

Result: **passed**. `vite build` completed.

## Live local stack (not Atlas, not Groq)

`BUILDSURE_STORAGE=local`. Embedding model `all-MiniLM-L6-v2` downloaded and used by `scripts/seed_repository.py`.

```text
cd Backend && BUILDSURE_STORAGE=local .venv/bin/python scripts/seed_repository.py --force
```

Result: **17 PDFs indexed** (8 global building codes, 9 project documents). Exit code 0. `--force` clears previous document rows, chunks, and `data/uploads/doc_*.pdf` before indexing.

`GET /api/health` after `uvicorn src.main:app --host 127.0.0.1 --port 8000`:

- `status`: healthy
- `storage`: local
- `vector_search`: cosine_fallback
- `llm_configured`: false
- `embedding_model`: all-MiniLM-L6-v2
- `embedding_dimensions`: 384

`POST /api/search` for the corridor question on Project Alpha returned extractive mode, cited `building_code_fire_safety.pdf` Section 7.2 Page 1 ("at least 1.0 m"), and did not say the 1.05 m width complies. An unrelated question returned exactly `No relevant compliance rule found in current repository.` with no source cards. A Block A inspection query returned that report for Project Beta and did not return it for Project Alpha.

Browser at `http://127.0.0.1:5173` (Vite proxy):

- Project menu loaded Project Alpha — Commercial Tower and Project Beta from the API.
- Alpha's library showed 8 global codes and 8 project PDFs. Block A was not in that list.
- The corridor question showed the loading line, then Section 7.2's quote, a `DEFICIENCY DETECTED` banner quoting Finding B-1 from `inspection_report_block_b.pdf` page 1, and source cards.
- View in PDF opened `building_code_fire_safety.pdf` page 1. The iframe URL was `/api/documents/doc_2c60700f/file?page=1#page=1`. Fetching that URL through the proxy returned `application/pdf` and body `%PDF-1.4`.

The first uvicorn process was started inside the sandbox and returned HTTP 503 on search because Hugging Face answered `ProxyError: 403` while loading the model. Restarting uvicorn outside the sandbox used the cached model. That 503 is an environment limit, not a retrieval logic failure.

## Not run

- Tests against a live MongoDB Atlas cluster or `$vectorSearch`.
- A live Groq completion. Citation tests use a fake client.
- A browser file-picker upload. Upload behavior is covered by the API tests.
- A mobile viewport pass.
- `scripts/ingest.py` against real ChromaDB. `chromadb` is not installed. Its unit tests inject a fake collection and passed.

## Mocked versus live

| Check | Mode |
|---|---|
| `pytest` (65) | In-memory store, keyword vectors, fake Groq client where a model response is needed |
| Seed, health, search, PDF bytes, browser flow | Real MiniLM embeddings, local JSON store, no Groq, no Atlas |
