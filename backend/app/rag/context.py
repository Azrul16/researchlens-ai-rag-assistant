import re
from functools import lru_cache

import tiktoken

from app.core.config import get_settings
from app.rag.prompts import MISSING


@lru_cache
def tokenizer():
    return tiktoken.get_encoding("cl100k_base")


def token_count(text: str) -> int:
    return len(tokenizer().encode(text, disallowed_special=()))


def build_context(sources: list[dict], budget: int | None = None):
    """Attach identifiers to trusted metadata; bound the total evidence token count."""
    remaining = budget or get_settings().context_token_budget
    retained, rendered = [], []
    for source in sources:
        source = {**source, "source_id": f"S{len(retained) + 1}"}
        passage = (
            f"[{source['source_id']}] Paper: {source['document_title']} "
            f"(document_id={source['document_id']}), page {source['page_number']}\n"
            + source["excerpt"]
        )
        size = token_count(passage)
        if size > remaining:
            continue
        retained.append(source)
        rendered.append(passage)
        remaining -= size
    return "UNTRUSTED SOURCE MATERIAL\n" + "\n\n".join(rendered), retained


def cited_sources(text: str, declared: list[str], sources: list[dict]):
    available = {source["source_id"]: source for source in sources}
    markers = re.findall(r"\[(S[^\]]*)\]", text)
    if any(not re.fullmatch(r"S\d+(?:\s*[,;]\s*S\d+)*", marker) for marker in markers):
        return None
    inline = [identifier for marker in markers for identifier in re.findall(r"S\d+", marker)]
    ids = set(declared) | set(inline)
    if not ids or not ids.issubset(available):
        return None
    return [source for source in sources if source["source_id"] in ids]


def numbers_supported(text: str, sources: list[dict]) -> bool:
    """Reject introduced numeric values; this is a guard, not a faithfulness proof."""
    text = re.sub(r"\[S\d+(?:\s*[,;]\s*S\d+)*\]", "", text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    pattern = r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][+-]?\d+)?"
    numbers = {value.replace(",", "") for value in re.findall(pattern, text)}
    source_numbers = {
        value.replace(",", "")
        for value in re.findall(pattern, " ".join(s["excerpt"] for s in sources))
    }
    return numbers.issubset(source_numbers)


def validate_finding(finding, sources):
    if finding.text == MISSING and not finding.source_ids:
        return
    retained = cited_sources(finding.text, finding.source_ids, sources)
    if retained is None or not numbers_supported(finding.text, retained):
        from app.core.errors import AppError

        raise AppError(
            502,
            "UNGROUNDED_ANALYSIS",
            "The AI analysis included unsupported citations or numbers. Please retry.",
        )
