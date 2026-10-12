"""Minimal text PDFs for tests and for seeding the sample repository.

pypdf can read these files. The generator only emits Latin-1 text, so
characters outside that set are replaced rather than dropped silently from
the page stream.
"""
import io


def blank_pdf() -> bytes:
    """A valid one-page PDF with no text operators."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def build_pdf_pages(page_texts: list[str]) -> bytes:
    """Build a PDF with one page per string. Page order is one-based."""
    if not page_texts:
        raise ValueError("At least one page is required")
    pages = [text.splitlines() or [""] for text in page_texts]
    return _render_pages(pages)


def build_text_pdf(text: str, lines_per_page: int = 40) -> bytes:
    """Wrap a plain-text document into a multi-page PDF."""
    lines: list[str] = []
    for raw in text.splitlines():
        if not raw.strip():
            lines.append("")
            continue
        current = ""
        for word in raw.split():
            candidate = word if not current else f"{current} {word}"
            if len(candidate) > 90 and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    if not lines:
        lines = [""]
    step = max(lines_per_page, 1)
    page_texts = ["\n".join(lines[index:index + step]) for index in range(0, len(lines), step)]
    return build_pdf_pages(page_texts)


def _escape(text: str) -> str:
    encoded = text.encode("latin-1", "replace").decode("latin-1")
    return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 11 Tf", "72 750 Td"]
    for index, line in enumerate(lines[:45]):
        if index:
            commands.append("0 -16 Td")
        commands.append(f"({_escape(line)}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", "replace")


def _render_pages(pages: list[list[str]]) -> bytes:
    count = len(pages)
    font_id = 3 + count * 2
    objects: dict[int, bytes] = {}
    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(count))
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Count {count} /Kids [{kids}] >>".encode()
    objects[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for index, lines in enumerate(pages):
        page_id = 3 + index * 2
        content_id = page_id + 1
        content = _content_stream(lines)
        objects[content_id] = (
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
        )
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        ).encode()

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj_id in range(1, font_id + 1):
        offsets.append(len(output))
        output.extend(f"{obj_id} 0 obj\n".encode())
        output.extend(objects[obj_id])
        output.extend(b"\nendobj\n")

    xref = len(output)
    output.extend(f"xref\n0 {font_id + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, font_id + 1):
        output.extend(f"{offsets[obj_id]:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {font_id + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)
