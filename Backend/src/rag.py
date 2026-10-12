"""Grounded compliance answers.

The model may only use retrieved chunks. Citations that do not match those
chunks are not shown. With no API key, the answer quotes the retrieved text
and says so. Retrieval scores are not described as probabilities.
"""
import logging
import os
import re
from typing import Optional

from src.config import GROQ_API_KEY, LLM_MODEL
from src.deficiencies import analyze_deficiencies, classify_chunk

logger = logging.getLogger(__name__)

NO_EVIDENCE = "No relevant compliance rule found in current repository."

COMPLIANCE_SYSTEM_PROMPT = (
    "You are a construction compliance retrieval assistant for site engineers. "
    "Answer using ONLY the provided document context. "
    "Do not state a requirement, measurement, page, section, or inspection finding "
    "that is not written in that context. "
    "After each material statement, cite it as [Document file name, Section ID, Page N]. "
    "If the context does not establish the answer, reply with exactly: "
    f"{NO_EVIDENCE} "
    "If an inspection excerpt says the finding is open or unresolved, say that an "
    "unresolved deficiency is documented and cite it. "
    "If the excerpt says the finding is closed or resolved, do not call it unresolved. "
    "If an inspection excerpt describes a problem but does not give a status, say the "
    "finding requires verification. "
    "Do not say the project is compliant just because no violation was retrieved."
)

_CITATION_RE = re.compile(r"\[([^\[\]\n]{1,300})\]")


def get_groq_client(api_key: Optional[str] = None):
    """Return a Groq client, or None when no key is configured."""
    key = api_key or GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    if not key:
        logger.warning("GROQ_API_KEY is not configured. Answers will quote retrieved text.")
        return None
    try:
        from groq import Groq
        return Groq(api_key=key)
    except ImportError:
        logger.error("groq package is not installed.")
        return None


def format_citation(chunk: dict) -> str:
    """Citation form required on material statements."""
    name = chunk.get("file_name") or chunk.get("source") or "Document"
    section = chunk.get("section_id") or chunk.get("section") or "section"
    page = int(chunk.get("page_number") or 1)
    return f"[{name}, {section}, Page {page}]"


def _citation_matches(inner: str, chunk: dict) -> bool:
    page = int(chunk.get("page_number") or 1)
    if re.search(rf"Page:?\s*{page}(?!\d)", inner, re.IGNORECASE) is None:
        return False
    name = (chunk.get("file_name") or chunk.get("source") or "").strip()
    if not name:
        return False
    haystack = inner.lower()
    if name.lower() not in haystack and name.rsplit(".", 1)[0].lower() not in haystack:
        return False
    section_id = (chunk.get("section_id") or "").strip()
    section = (chunk.get("section") or "").strip()
    if section_id and section_id.lower() in haystack:
        return True
    if section and section.lower() in haystack:
        return True
    return False


def citations_are_grounded(answer: str, chunks: list[dict]) -> bool:
    """True only when every bracket citation matches a retrieved chunk."""
    found = _CITATION_RE.findall(answer or "")
    if not found:
        return False
    return all(any(_citation_matches(inner, chunk) for chunk in chunks) for inner in found)


def citations_from_answer(answer: str, chunks: list[dict]) -> list[dict]:
    """Keep citation records that match retrieved metadata."""
    citations = []
    seen = set()
    for inner in _CITATION_RE.findall(answer or ""):
        match = next((chunk for chunk in chunks if _citation_matches(inner, chunk)), None)
        if match is None or inner in seen:
            continue
        seen.add(inner)
        citations.append({
            "label": inner.strip(),
            "scope": "local" if match.get("scope") == "project" else "global",
            "documentName": match.get("file_name") or match.get("source") or "",
        })
    return citations


def format_context_for_prompt(chunks: list[dict]) -> str:
    """Format retrieved chunks as the only context the model may use."""
    entries = []
    for index, chunk in enumerate(chunks, 1):
        filename = chunk.get("file_name") or chunk.get("source") or "Unknown Document"
        section = chunk.get("section") or "General"
        section_id = chunk.get("section_id") or ""
        page = chunk.get("page_number", 1)
        scope = chunk.get("scope", "global")
        doc_type = chunk.get("doc_type", "building_code")
        quote = (chunk.get("quote") or chunk.get("text") or "").strip()
        entries.append(
            f"--- Context Block {index} ---\n"
            f"Document: {filename}\n"
            f"Section: {section}\n"
            f"Section ID: {section_id}\n"
            f"Page: {page}\n"
            f"Scope: {scope} | Type: {doc_type}\n"
            f"Allowed citation: {format_citation(chunk)}\n"
            f"Text:\n{quote}\n"
        )
    return "\n".join(entries)


def _extractive(chunks: list[dict], preface: str) -> dict:
    """Quote retrieved text. This is not a model-written compliance ruling."""
    lines = [
        preface,
        "This summary quotes retrieved repository text only. "
        "It does not decide compliance for conditions the excerpts do not state. "
        "A missing inspection finding is not proof of compliance.",
    ]
    citations = []
    seen = set()
    for chunk in chunks:
        cite = format_citation(chunk)
        quote = (chunk.get("quote") or chunk.get("text") or "").strip()
        section = chunk.get("section") or "Section"
        lines.append(f"{section}: \"{quote}\" {cite}")
        inner = cite[1:-1]
        if inner not in seen:
            seen.add(inner)
            citations.append({
                "label": inner,
                "scope": "local" if chunk.get("scope") == "project" else "global",
                "documentName": chunk.get("file_name") or chunk.get("source") or "",
            })

    report = analyze_deficiencies(chunks)
    if report.has_deficiency:
        lines.append(
            "A retrieved inspection report documents an unresolved deficiency. "
            "The deficiency warning lists the finding, source, and page."
        )
    elif report.status == "requires_verification":
        lines.append(
            "A retrieved inspection finding does not establish whether it is still unresolved. "
            "It requires verification."
        )
    elif any(classify_chunk(chunk) == "closed" for chunk in chunks):
        lines.append(
            "Retrieved inspection findings marked closed are historical and are not treated as unresolved deficiencies."
        )

    return {
        "answer": "\n\n".join(lines),
        "citations": citations,
        "generation_mode": "extractive",
    }


def _complete(client, model: str, query: str, chunks: list[dict], correction: str = "") -> str:
    context = format_context_for_prompt(chunks)
    extra = f"\n\n{correction}" if correction else ""
    user_prompt = (
        f"Document Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer strictly from the context. "
        f"If the context does not establish the answer, output exactly: {NO_EVIDENCE} "
        "Cite material statements as [Document file name, Section ID, Page N]. "
        "Do not declare the project compliant merely because no violation appears above."
        f"{extra}"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": COMPLIANCE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=1024,
    )
    return (response.choices[0].message.content or "").strip()


def generate_compliance_answer(
    query: str,
    retrieved_chunks: list[dict],
    client=None,
    model: str = LLM_MODEL,
) -> dict:
    """Answer from retrieved chunks, or return the no-evidence sentence."""
    if not retrieved_chunks:
        return {"answer": NO_EVIDENCE, "citations": [], "generation_mode": "no_evidence"}

    groq_client = client if client is not None else get_groq_client()
    if groq_client is None:
        return _extractive(
            retrieved_chunks,
            "The language model is not configured (GROQ_API_KEY is missing).",
        )

    allowed = ", ".join(format_citation(chunk) for chunk in retrieved_chunks)
    try:
        first = _complete(groq_client, model, query, retrieved_chunks)
    except Exception:
        logger.exception("Language model request failed")
        extracted = _extractive(retrieved_chunks, "The language model request failed.")
        extracted["generation_mode"] = "extractive_after_llm_error"
        return extracted

    if first == NO_EVIDENCE:
        return {"answer": NO_EVIDENCE, "citations": [], "generation_mode": "no_evidence"}
    if citations_are_grounded(first, retrieved_chunks):
        return {
            "answer": first,
            "citations": citations_from_answer(first, retrieved_chunks),
            "generation_mode": "llm",
        }

    try:
        second = _complete(
            groq_client,
            model,
            query,
            retrieved_chunks,
            correction=(
                "Your previous citations did not match the retrieved records. "
                f"Use only these citations: {allowed}"
            ),
        )
    except Exception:
        logger.exception("Language model retry failed")
        second = ""

    if second == NO_EVIDENCE:
        return {"answer": NO_EVIDENCE, "citations": [], "generation_mode": "no_evidence"}
    if second and citations_are_grounded(second, retrieved_chunks):
        return {
            "answer": second,
            "citations": citations_from_answer(second, retrieved_chunks),
            "generation_mode": "llm",
        }

    extracted = _extractive(
        retrieved_chunks,
        "The model response was not shown because its citations did not match retrieved sources.",
    )
    extracted["generation_mode"] = "extractive_after_citation_check"
    return extracted
