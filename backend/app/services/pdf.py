import re
from collections import Counter
from dataclasses import dataclass

import pymupdf

from app.core.config import get_settings
from app.core.errors import AppError
from app.rag.context import token_count

HEADINGS = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s+)?(abstract|introduction|related work|literature review|"
    r"methodology|methods|materials and methods|dataset[s]?|experimental setup|"
    r"experiments|results|discussion|conclusion[s]?|limitations|future work|references)$",
    re.IGNORECASE,
)


@dataclass
class Passage:
    page_number: int
    section_title: str | None
    content: str
    token_count: int


def clean_text(text: str) -> str:
    """Fix extraction artifacts without removing scientific symbols."""
    text = text.replace("\x00", "")
    text = re.sub(r"(?<=\w)-\n(?=[a-z])", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_units(text: str, limit: int, separators=("\n\n", "\n", ". ", "; ", " ")):
    """Recursively retain natural boundaries, with a token fallback for oversized units."""
    if token_count(text) <= limit:
        return [text]
    if separators:
        separator = separators[0]
        parts = text.split(separator)
        if len(parts) > 1:
            result = []
            for i, part in enumerate(parts):
                unit = part + (separator if i < len(parts) - 1 else "")
                result.extend(split_units(unit, limit, separators[1:]))
            return result
        return split_units(text, limit, separators[1:])
    midpoint = len(text) // 2
    if midpoint == 0:
        raise ValueError("Chunk limit cannot fit a single Unicode character")
    return split_units(text[:midpoint], limit, ()) + split_units(text[midpoint:], limit, ())


def token_suffix(text: str, limit: int) -> str:
    """Keep overlap within its token budget without slicing a UTF-8 token in half."""
    low, high = 0, len(text)
    while low < high:
        midpoint = (low + high + 1) // 2
        if token_count(text[-midpoint:]) <= limit:
            low = midpoint
        else:
            high = midpoint - 1
    return text[-low:] if low else ""


def split_page(
    text: str, page: int, size: int, overlap: int, initial_section=None
) -> list[Passage]:
    """Recursive token-bounded splitting; never merge unrelated source pages or sections."""
    passages, blocks = [], []
    section, buffer = initial_section, ""
    lines = []
    for line in text.splitlines():
        match = HEADINGS.fullmatch(line.strip())
        if match:
            if lines:
                blocks.append((section, "\n".join(lines)))
                lines = []
            section = match.group(1).title()
        lines.append(line)
    if lines:
        blocks.append((section, "\n".join(lines)))
    for section, block in blocks:
        buffer = ""
        for unit in split_units(block, size):
            if buffer and token_count(buffer + unit) > size:
                content = buffer.strip()
                passages.append(Passage(page, section, content, token_count(content)))
                buffer = token_suffix(buffer, overlap) if overlap else ""
                if token_count(buffer + unit) > size:
                    buffer = ""
            buffer += unit
        if buffer.strip():
            content = buffer.strip()
            passages.append(Passage(page, section, content, token_count(content)))
    return passages


def parse_pdf(payload: bytes, size: int, overlap: int):
    """Validate a PDF and return its metadata and page-grounded passages."""
    if not payload.startswith(b"%PDF-"):
        raise AppError(415, "INVALID_PDF", "The file does not contain a valid PDF header.")
    try:
        with pymupdf.open(stream=payload, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise AppError(422, "ENCRYPTED_PDF", "Please upload an unencrypted PDF.")
            if pdf.page_count == 0:
                raise AppError(422, "EMPTY_PDF", "This PDF has no pages.")
            if pdf.page_count > get_settings().max_pdf_pages:
                raise AppError(413, "TOO_MANY_PAGES", "The PDF exceeds the configured page limit.")
            pages = [clean_text(page.get_text()) for page in pdf]
            if len(pages) >= 3:
                boundaries = Counter(
                    line
                    for text in pages
                    for line in (text.splitlines()[:1] + text.splitlines()[-1:])
                    if len(line) > 12 and not HEADINGS.fullmatch(line.strip())
                )
                repeated = {
                    line for line, count in boundaries.items() if count >= max(3, len(pages) * 0.6)
                }
                cleaned = []
                for text in pages:
                    lines = text.splitlines()
                    if lines and lines[0] in repeated:
                        lines.pop(0)
                    if lines and lines[-1] in repeated:
                        lines.pop()
                    cleaned.append("\n".join(lines))
                pages = cleaned
            metadata = pdf.metadata or {}
            title = metadata.get("title") or next(
                (line for text in pages for line in text.splitlines() if len(line) > 8), None
            )
            authors = [metadata["author"]] if metadata.get("author") else []
            passages, section = [], None
            for number, text in enumerate(pages, 1):
                page_chunks = split_page(text, number, size, overlap, section)
                passages.extend(page_chunks)
                if page_chunks:
                    section = page_chunks[-1].section_title
            abstract_match = re.search(
                r"(?is)(?:^|\n)abstract\s*\n(.+?)(?=\n(?:\d+\.?\s+)?introduction|$)",
                "\n".join(pages[:2]),
            )
            return {
                "title": title[:500] if title else None,
                "authors": authors,
                "abstract": abstract_match.group(1).strip()[:8000] if abstract_match else None,
                "page_count": len(pages),
                "passages": passages,
                "scanned": sum(len(text) for text in pages) < 40,
            }
    except AppError:
        raise
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise AppError(422, "MALFORMED_PDF", "The PDF could not be read.") from exc
