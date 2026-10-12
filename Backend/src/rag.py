"""Groq LLM integration and strict compliance RAG answer generation."""
import logging
import os
import re
from typing import Optional

from src.config import GROQ_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

COMPLIANCE_SYSTEM_PROMPT = (
    "You are an expert construction compliance assistant for site engineers. "
    "Answer the question using ONLY the provided document context. "
    "If the answer cannot be explicitly verified, state 'No relevant compliance rule found in project repository.' "
    "Force inline citations containing document name, section, and page number in the format "
    "[Document: <document_name>, Section: <section>, Page: <page_number>]. "
    "Do not extrapolate, assume, or cite external regulations not present in the provided context."
)

NO_COMPLIANCE_FOUND_MSG = "No relevant compliance rule found in project repository."


def get_groq_client(api_key: Optional[str] = None):
    """Initialize and return the Groq client instance."""
    key = api_key or GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    if not key:
        logger.warning("GROQ_API_KEY not configured. Answers will require API key.")
        return None
    try:
        from groq import Groq
        return Groq(api_key=key)
    except ImportError:
        logger.error("groq package is not installed.")
        return None


def format_context_for_prompt(chunks: list[dict]) -> str:
    """Format retrieved vector chunks into structured context blocks."""
    if not chunks:
        return ""
    entries = []
    for idx, c in enumerate(chunks, 1):
        filename = c.get("file_name") or c.get("source") or "Unknown Document"
        section = c.get("section") or "General"
        page = c.get("page_number", 1)
        scope = c.get("scope", "global")
        doc_type = c.get("doc_type", "building_code")
        text = c.get("text", "").strip()

        entries.append(
            f"--- Context Block {idx} ---\n"
            f"Document: {filename}\n"
            f"Section: {section}\n"
            f"Page: {page}\n"
            f"Scope: {scope} | Type: {doc_type}\n"
            f"Text:\n{text}\n"
        )
    return "\n".join(entries)


def parse_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """Parse citations from the answer or link against provided chunks."""
    citations = []
    seen = set()

    # Pattern matching [Document: X, Section: Y, Page: Z] or [X, Sec Y, Page Z]
    citation_pattern = re.compile(
        r"\[Document:\s*([^,\]]+),\s*Section:\s*([^,\]]+),\s*Page:\s*(\d+)\]",
        re.IGNORECASE,
    )

    for match in citation_pattern.finditer(answer):
        doc_name, section, page = match.groups()
        label = f"{section.strip()}, Page {page.strip()}"
        key = (doc_name.strip(), label)
        if key not in seen:
            seen.add(key)
            citations.append({
                "label": label,
                "scope": "local" if any(c.get("scope") == "project" for c in chunks if doc_name in str(c.get("file_name"))) else "global",
                "documentName": doc_name.strip(),
            })

    # If no inline brackets matched but chunks were used, create citations from top chunks
    if not citations and answer != NO_COMPLIANCE_FOUND_MSG and chunks:
        for c in chunks[:3]:
            doc_name = c.get("file_name") or c.get("source") or c.get("title", "")
            sec = c.get("section") or "General"
            pg = c.get("page_number", 1)
            label = f"{sec}, Page {pg}"
            key = (doc_name, label)
            if key not in seen:
                seen.add(key)
                citations.append({
                    "label": label,
                    "scope": "local" if c.get("scope") == "project" else "global",
                    "documentName": doc_name,
                })

    return citations


def generate_compliance_answer(
    query: str,
    retrieved_chunks: list[dict],
    client=None,
    model: str = LLM_MODEL,
) -> dict:
    """Generate a strict compliance answer using Groq and the provided document chunks."""
    if not retrieved_chunks:
        return {
            "answer": NO_COMPLIANCE_FOUND_MSG,
            "citations": [],
        }

    context_str = format_context_for_prompt(retrieved_chunks)
    groq_client = client if client is not None else get_groq_client()

    if groq_client is None:
        # Fallback if no GROQ_API_KEY is configured
        fallback_msg = (
            f"Retrieved {len(retrieved_chunks)} relevant compliance chunk(s), but GROQ_API_KEY is not configured.\n"
            f"Top match: {retrieved_chunks[0].get('file_name')} ({retrieved_chunks[0].get('section')}, Page {retrieved_chunks[0].get('page_number')})."
        )
        return {
            "answer": fallback_msg,
            "citations": parse_citations(fallback_msg, retrieved_chunks),
        }

    user_prompt = (
        f"Document Context:\n{context_str}\n\n"
        f"Question: {query}\n\n"
        f"Remember: Answer strictly using ONLY the above context. If the answer cannot be explicitly verified, "
        f"output exactly: '{NO_COMPLIANCE_FOUND_MSG}'. "
        f"Include inline citations like [Document: <filename>, Section: <section>, Page: <page_number>]."
    )

    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": COMPLIANCE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=1024,
        )
        raw_answer = response.choices[0].message.content.strip()
        citations = parse_citations(raw_answer, retrieved_chunks)
        return {
            "answer": raw_answer,
            "citations": citations,
        }
    except Exception as exc:
        logger.error(f"Error during Groq LLM completion: {exc}")
        return {
            "answer": f"Error generating compliance response: {str(exc)}",
            "citations": [],
        }
