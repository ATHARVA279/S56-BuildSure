# Product Requirements Document

## RegFind — AI Compliance Assistant for Site Engineers

*Simulated Work · Odd Semester 2026–27 · Sprint 2 (AI Application) · Team 03*

---

## Document Control

| Field | Detail |
|---|---|
| Team | Team 03 |
| Sprint | Sprint 2 — AI Application (RAG) |
| Phase | Phase 2 — PRD |
| Status | Draft — pending mentor approval |
| Version | v1.0 |

---

## 1. Problem Statement

A construction firm maintains building codes, project specifications, and inspection reports, but site engineers cannot quickly confirm which regulation applies, risking costly compliance errors.

Today, this information is spread across long PDFs and scanned reports. When a site engineer needs to confirm a rule on-site (e.g., minimum rebar spacing, fire-exit clearance), they must manually search multiple documents — slow, error-prone, and risky when a wrong or missed regulation leads to rework, safety issues, or compliance penalties.

## 2. Goal

Build a Retrieval-Augmented Generation (RAG) assistant that lets a site engineer type a plain-English question and instantly get the exact applicable regulation, with the source document and clause cited — so they trust the answer enough to act on it.

## 3. Target User

- **Primary:** Site engineers who need a fast, trustworthy answer while on-site or in a review meeting.
- **Secondary:** Project managers / QA leads who spot-check compliance before sign-off.

## 4. Scope (Keep It Easy — MVP First)

### In Scope

- A fixed, curated set of ~15–25 sample documents (building codes, specs, inspection reports) in PDF/text — mocked or drawn from public building-code excerpts.
- Document ingestion pipeline: load → clean → chunk → embed → store in a vector database.
- A simple chat/search interface: engineer types a question, gets an answer + the source clause + document name.
- Basic citation: every answer must show which document and section it came from.

### Out of Scope (for this sprint)

- Live document uploads by end users (documents are pre-loaded by the team).
- Multi-user accounts, roles, or authentication.
- Automated regulation updates / web scraping of new codes.
- Mobile app — a working web UI is enough.

## 5. User Stories

- As a site engineer, I can type "What is the minimum rebar spacing for a slab?" and get a direct answer with the source clause, so I don't have to search PDFs manually.
- As a site engineer, I can see which document and page/section the answer came from, so I can verify it myself.
- As a project manager, I can ask about inspection report findings for a given issue, so I can confirm what was flagged.
- As a user, if the system is unsure, I want it to say so rather than guess, so I don't act on a wrong answer.

## 6. Functional Requirements

| ID | Requirement |
|---|---|
| FR1 | System ingests a folder of PDFs/text docs and splits them into retrievable chunks. |
| FR2 | System generates embeddings for each chunk and stores them in a vector index. |
| FR3 | User submits a natural-language question via a simple web UI. |
| FR4 | System retrieves the top-k most relevant chunks and passes them to an LLM to generate a grounded answer. |
| FR5 | Every answer displays the source document name and the retrieved text snippet. |
| FR6 | If no relevant chunk is found above a confidence/similarity threshold, the system responds "No confident match found" instead of guessing. |

## 7. Non-Functional Requirements

- Answers return in under ~5 seconds for the demo dataset.
- Runs locally / on free-tier infra — no paid infrastructure required for the MVP.
- Simple enough that a 2–3 person team can build, test, and demo it within the sprint timeline.

## 8. System Architecture (High Level)

```
Documents → Text Extraction → Chunking → Embedding Model → Vector Store
          → Retriever → LLM (with retrieved context) → Answer + Citation → Web UI
```

- **Ingestion Lane:** load documents, clean text, chunk (e.g., 300–500 tokens with overlap).
- **Retrieval Lane:** embed chunks, store/query a vector database, return top-k matches.
- **Generation Lane:** prompt the LLM with the question + retrieved chunks, format the answer with citations.
- **Interface Lane:** a minimal web app for asking questions and viewing answers + sources.

## 9. Recommended Tech Stack (Easy / Low-Cost)

| Layer | Recommended Choice |
|---|---|
| Document parsing | PyPDF2 / pdfplumber (Python) |
| Chunking + orchestration | LangChain or plain Python (simple splitter) |
| Embeddings | sentence-transformers (free, runs locally, no API key) |
| Vector store | ChromaDB or FAISS (free, local, no server setup) |
| LLM for generation | Free-tier API (e.g., Groq / Gemini) or OpenAI if the team has credits |
| Frontend | Streamlit (fastest way to ship a usable UI) |
| Version control | Git + GitHub, all changes via PR |

## 10. Success Metrics

- Retrieval accuracy: top-3 retrieved chunks contain the correct regulation for ≥80% of a 15–20 question test set.
- Every answer shown in the demo includes a visible, correct source citation.
- Live demo runs end-to-end without manual intervention on Showcase Day.

## 11. Contribution Lanes (Fill In With Your Team)

- **Member 1 — Ingestion & Retrieval:** document loading, chunking, embeddings, vector store.
- **Member 2 — Generation & Prompting:** LLM integration, prompt design, citation formatting, confidence threshold.
- **Member 3 — Interface & Integration:** Streamlit UI, connecting retrieval + generation, testing, demo prep.

*(Adjust lanes to your team size — each lane must be a named, documented set of responsibilities, not "I'll help wherever needed.")*

## 12. Risks & Assumptions

- **Risk:** Sample documents may not have clean, extractable text (scanned images) — mitigate by choosing clean PDFs or doing light OCR only if needed.
- **Risk:** LLM may hallucinate outside the retrieved context — mitigate with a strict prompt ("Answer only from the provided context") and the confidence threshold in FR6.
- **Assumption:** Mentor approves a fixed, small sample-document set for the MVP rather than requiring full real-world code coverage.

## 13. Milestones (aligned to Sprint Build Model)

| Phase | Target |
|---|---|
| Learning | Understand RAG, embeddings, vector search, and the compliance domain. |
| PRD (this doc) | Agreed scope, requirements, and success metrics. |
| System Design | Architecture diagram, data flow, contribution lanes finalized. |
| Approvals | Mentor reviews and signs off before implementation starts. |
| Implementation | Build in small PRs: ingestion → retrieval → generation → UI → polish. |
| Showcase + Viva | Live demo of an end-to-end question → grounded answer with citation. |
