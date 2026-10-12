"""Index the fictional sample documents into the active document store.

Usage, from the Backend directory:

    python scripts/seed_repository.py
    python scripts/seed_repository.py --force

Building codes are stored in the global repository. Specifications and
inspection reports are stored on Project Alpha, except the Block A inspection
report, which is stored on Project Beta so project isolation can be checked.
Original text is wrapped in a PDF so the viewer can open a real file.
"""
import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DOCS_DIR, UPLOAD_DIR  # noqa: E402
from src.db import get_chunks_collection, get_documents_collection, get_projects_collection, init_db  # noqa: E402
from src.ingestion import ingest_pdf_bytes  # noqa: E402
from src.pdf_util import build_text_pdf  # noqa: E402


def ensure_project(name: str, location: str) -> str:
    projects = get_projects_collection()
    existing = projects.find_one({"name": name})
    if existing:
        return existing["id"]
    project_id = f"proj-{uuid.uuid4().hex[:8]}"
    projects.insert_one(
        {
            "id": project_id,
            "name": name,
            "location": location,
            "is_global": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return project_id


def classify(filename: str) -> tuple[str, str]:
    lowered = filename.lower()
    if lowered.startswith("building_code"):
        return "global", "building_code"
    if lowered.startswith("inspection"):
        return "project", "inspection_report"
    return "project", "specification"


def already_indexed(file_name: str, project_id: str) -> bool:
    document = get_documents_collection().find_one(
        {"file_name": file_name, "project_id": project_id, "processing_status": "indexed"}
    )
    return document is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed BuildSure with the fictional sample documents")
    parser.add_argument("--force", action="store_true", help="Index again even if a matching file is already stored")
    args = parser.parse_args()

    init_db()
    if args.force:
        get_documents_collection().delete_many({})
        get_chunks_collection().delete_many({})
        if UPLOAD_DIR.exists():
            for stored in UPLOAD_DIR.glob("doc_*.pdf"):
                stored.unlink()
        print("Cleared previously seeded documents")
    alpha = ensure_project("Project Alpha — Commercial Tower", "Site 44")
    beta = ensure_project("Project Beta", "Site 12")
    print(f"Project Alpha: {alpha}")
    print(f"Project Beta: {beta}")

    paths = sorted(path for path in Path(DOCS_DIR).glob("*.txt") if path.is_file())
    if not paths:
        print(f"No sample documents in {DOCS_DIR}")
        return 1

    indexed = 0
    for path in paths:
        scope, doc_type = classify(path.name)
        if path.name == "inspection_report_block_a.txt":
            project_id = beta
        elif scope == "global":
            project_id = "global"
        else:
            project_id = alpha
        pdf_name = f"{path.stem}.pdf"
        if not args.force and already_indexed(pdf_name, project_id):
            print(f"skip {pdf_name}")
            continue
        pdf_bytes = build_text_pdf(path.read_text(encoding="utf-8"))
        result = ingest_pdf_bytes(
            file_bytes=pdf_bytes,
            filename=pdf_name,
            project_id=project_id,
            scope=scope,
            doc_type=doc_type,
        )
        indexed += 1
        print(
            f"indexed {result['file_name']} -> {result['project_id']} "
            f"({result['chunks_stored']} chunks, {result['pages_processed']} pages)"
        )

    print(f"Done. Newly indexed: {indexed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())