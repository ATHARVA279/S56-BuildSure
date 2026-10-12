# BuildSure — RegFind

An AI compliance assistant for construction site engineers. Ask a plain-English
question and get the applicable regulation, with the source document and clause cited.

> Sprint 2 (AI Application) · Simulated Work · Team 03

**Problem:** A construction firm maintains building codes, project specifications,
and inspection reports, but site engineers cannot quickly confirm which regulation
applies, risking costly compliance errors.

**Approach:** Retrieval-Augmented Generation (RAG). Documents are chunked, embedded
and stored in a vector database. For each question, the most relevant chunks are
retrieved and an LLM answers using only that context, citing its sources.

## Documentation

- [Product Requirements (PRD)](docs/PRD.md)
- [System Design](docs/SYSTEM_DESIGN.md)

## Project structure

```
data/sample_docs/   Sample documents (fictional, for demonstration only)
src/                Pipeline code (loader, chunker, embedder, retriever, LLM, ...)
scripts/            ingest.py, evaluate.py
tests/              Unit tests and evaluation questions
app.py              Streamlit UI
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then add your GROQ_API_KEY
```

## Status

Work in progress. Setup instructions for ingesting documents and running the app
will be added as each component lands.

## Disclaimer

All sample documents in this repository are fictional and for demonstration only.
They are not real building codes or regulations.
