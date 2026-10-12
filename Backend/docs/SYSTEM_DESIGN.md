# System Design

## RegFind — AI Compliance Assistant for Site Engineers

*Simulated Work · Sprint 2 (AI Application) · Team 03*
*Phase 3 — System Design · Status: Draft — pending mentor approval*

---

## 1. Overview

RegFind is a Retrieval-Augmented Generation (RAG) application. A site engineer asks a plain-English compliance question, the system finds the most relevant clauses from a fixed set of building codes, specifications and inspection reports, and an LLM writes a short answer grounded **only** in those clauses, with the source document cited.

This document describes how the system is built. Scope and requirements are in `docs/PRD.md`.

## 2. Architecture

```
                         ┌──────────────── OFFLINE (run once) ────────────────┐
                         │                                                    │
 data/sample_docs/*.txt ─▶ Loader ─▶ Chunker ─▶ Embedder ─▶ Vector Store      │
                         │ (text +   (400-token  (MiniLM)    (ChromaDB,       │
                         │ metadata)  chunks)               persisted)        │
                         └────────────────────────────────────────┬───────────┘
                                                                  │
                         ┌──────────────── ONLINE (per question) ─┼───────────┐
                         │                                        ▼           │
 Engineer ─▶ Streamlit ─▶ RAG Pipeline ─▶ Retriever ─────▶ top-k chunks       │
   question     UI          │              (embed question,     + scores      │
                ▲           │               query store)            │         │
                │           │                                       ▼         │
                │           │            Confidence check ──(low)──▶ "No confident
                │           │              (similarity threshold)     match found"
                │           │                      │(ok)                      │
                │           ▼                      ▼                          │
                │      Prompt Builder ─▶ LLM (Groq API) ─▶ Answer + Citations │
                │                                                  │          │
                └──────────────────────────────────────────────────┘          │
                         └────────────────────────────────────────────────────┘
```

## 3. Components

| Component | File | Responsibility |
|---|---|---|
| Loader | `src/loader.py` | Reads every `.txt` file in `data/sample_docs/`; returns text plus metadata (filename, document type). |
| Chunker | `src/chunker.py` | Splits text into ~400-token chunks with ~50-token overlap; keeps source filename and section heading with each chunk. |
| Embedder | `src/embedder.py` | Converts text to vectors using `sentence-transformers` (`all-MiniLM-L6-v2`), run locally. |
| Vector Store | `src/vector_store.py` | Stores chunk vectors and metadata in ChromaDB (persisted to `chroma_db/`); supports add and similarity query. |
| Retriever | `src/retriever.py` | Embeds the question, queries the store, returns top-k chunks with similarity scores. |
| Prompt Builder | `src/prompts.py` | Builds the LLM prompt: instructions + retrieved chunks + question. |
| LLM Client | `src/llm.py` | Calls the Groq API; API key read from `.env`. |
| RAG Pipeline | `src/rag_pipeline.py` | Orchestrates retrieve → confidence check → prompt → LLM → formatted answer with sources. |
| UI | `app.py` | Streamlit page: question box, answer, expandable source snippets. |
| Ingest script | `scripts/ingest.py` | One command that runs loader → chunker → embedder → vector store. |
| Eval script | `scripts/evaluate.py` | Runs the question set and reports top-3 retrieval accuracy. |

## 4. Data Flow

### 4.1 Ingestion (offline, run once or when documents change)

1. `ingest.py` calls the Loader to read all documents.
2. Chunker splits each document into overlapping chunks, attaching `{source, section, chunk_id}`.
3. Embedder converts each chunk to a vector.
4. Vector Store saves vector + text + metadata to ChromaDB.

### 4.2 Question answering (online, per question)

1. Engineer types a question in the Streamlit UI.
2. Pipeline asks the Retriever for the top-k (k = 4) chunks.
3. **Confidence check:** if the best similarity score is below the threshold, return *"No confident match found"* and skip the LLM (FR6).
4. Prompt Builder inserts the chunks and the question into the prompt template.
5. LLM returns an answer grounded in the supplied chunks.
6. Pipeline returns the answer plus the source filename and snippet of each chunk used (FR5).
7. UI displays the answer and a collapsible "Sources" panel.

## 5. Data Model

**Chunk record (stored in ChromaDB)**

| Field | Example |
|---|---|
| `id` | `building_code_01_chunk_07` |
| `text` | "Section 4.2 Rebar Spacing: ..." |
| `embedding` | 384-dimension vector |
| `metadata.source` | `building_code_01.txt` |
| `metadata.doc_type` | `building_code` / `specification` / `inspection_report` |
| `metadata.section` | `4.2 Rebar Spacing` |

**Pipeline response (returned to UI)**

```json
{
  "answer": "string",
  "confident": true,
  "sources": [
    { "source": "building_code_01.txt", "section": "4.2", "snippet": "...", "score": 0.78 }
  ]
}
```

## 6. Key Design Decisions

| Decision | Choice | Why |
|---|---|---|
| Document format | `.txt` sample documents | Removes PDF-extraction risk; focus stays on the RAG pipeline. |
| Embeddings | `all-MiniLM-L6-v2` (local) | Free, no API key, fast on CPU. |
| Vector store | ChromaDB (persisted) | No server to run; simple Python API. |
| LLM | Groq free tier | Free, fast; swappable behind `llm.py`. |
| Chunk size | ~400 tokens, ~50 overlap | Large enough to hold a full clause; tunable after evaluation. |
| Retrieval | top-k = 4 | Enough context without overloading the prompt; tunable. |
| Hallucination control | Strict prompt + similarity threshold | LLM may only use supplied context; weak matches are refused. |
| UI | Streamlit | Fastest route to a usable demo. |

## 7. Prompt Design (draft)

```
You are a compliance assistant for construction site engineers.
Answer the question using ONLY the context below.
If the context does not contain the answer, reply exactly: "No confident match found."
Always name the source document and section you used.

Context:
{retrieved_chunks_with_sources}

Question: {question}
```

## 8. Error Handling

| Situation | Behaviour |
|---|---|
| Empty question | UI asks the user to type a question; no pipeline call. |
| Vector store missing | UI shows "Run `python scripts/ingest.py` first." |
| LLM API failure / timeout | UI shows a clear error; retrieved sources are still displayed. |
| Low similarity | "No confident match found" (no LLM call). |

## 9. Security & Configuration

- API keys live in `.env` (git-ignored); `.env.example` documents required variables.
- `chroma_db/` and `venv/` are git-ignored.
- All documents are fictional sample content, labelled as such in the README.

## 10. Testing & Evaluation

- **Retrieval accuracy:** `scripts/evaluate.py` runs 15–20 questions from `tests/eval_questions.json`; target ≥ 80% where the correct source appears in the top 3 results.
- **Unit tests (pytest):** chunker output sizes/overlap, retriever returns k results, fallback triggers below threshold.
- **Demo check:** four rehearsed questions run end-to-end before showcase.

## 11. Contribution Lanes

Solo build — a single owner covers every lane, delivered through small pull requests:

| Lane | Components | Owner |
|---|---|---|
| Ingestion & Retrieval | Loader, Chunker, Embedder, Vector Store, Retriever, Ingest script | Joyce Ubale |
| Generation & Prompting | Prompt Builder, LLM Client, RAG Pipeline, confidence fallback, citations | Joyce Ubale |
| Interface & Quality | Streamlit UI, error handling, evaluation, tests, README, demo script | Joyce Ubale |

## 12. Build Order (PR plan)

Scaffold → sample docs → loader → chunker → embedder → vector store → ingest script → retriever → eval question set → LLM client → prompt builder → citations → confidence fallback → RAG pipeline → Streamlit UI → eval script → tuning → error handling → tests → README → demo script.

## 13. Open Questions for Mentor

1. Are PRs counted on the personal fork or the team repository?
2. Is a fictional/sample document set acceptable for the demo?
3. Is Groq (free tier) an acceptable LLM provider?
