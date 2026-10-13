import logging
import re
import time

from app.core.config import get_settings
from app.llm.factory import get_llm_provider
from app.rag.context import build_context, cited_sources, numbers_supported
from app.rag.prompts import INSUFFICIENT, SYSTEM_PROMPT
from app.schemas_ai import AnswerOut, GeneratedAnswer
from app.services.vector_store import retrieve

logger = logging.getLogger(__name__)


async def answer_question(db, workspace_id: str, question: str, history: list[dict], document_ids):
    """Fresh retrieval, bounded context, validated generation and trusted citations."""
    start = time.perf_counter()
    # Bounded user turns help resolve follow-ups without treating old answers as evidence.
    recent_questions = [m["content"] for m in history if m["role"] == "user"][-2:]
    followup = len(question.split()) < 8 or bool(
        re.search(r"\b(it|they|that|these|this|second|first|previous)\b", question.lower())
    )
    query = "\n".join([*recent_questions, question]) if recent_questions and followup else question
    sources = await retrieve(db, workspace_id, query, document_ids)
    if not sources:
        return AnswerOut(answer=INSUFFICIENT, sources=[], sufficient_evidence=False)
    context, sources = build_context(sources[: get_settings().final_context_k])
    if not sources:
        return AnswerOut(answer=INSUFFICIENT, sources=[], sufficient_evidence=False)
    retrieval_ms = (time.perf_counter() - start) * 1000
    messages = [*history, {"role": "user", "content": f"Question: {question}\n\n{context}"}]
    generated = await get_llm_provider().generate_structured(
        SYSTEM_PROMPT, messages, GeneratedAnswer
    )
    retained = cited_sources(generated.answer, generated.source_ids, sources)
    if (
        not generated.sufficient_evidence
        or retained is None
        or not numbers_supported(generated.answer, retained)
    ):
        logger.info(
            "rag_evidence_refused workspace_id=%s provider_sufficient=%s citations_valid=%s",
            workspace_id,
            generated.sufficient_evidence,
            retained is not None,
        )
        return AnswerOut(answer=INSUFFICIENT, sources=[], sufficient_evidence=False)
    logger.info(
        "rag workspace_id=%s chunks=%s retrieval_ms=%.1f total_ms=%.1f",
        workspace_id,
        len(retained),
        retrieval_ms,
        (time.perf_counter() - start) * 1000,
    )
    answer = generated.answer
    if "[S" not in answer:
        answer += " " + " ".join(f"[{source['source_id']}]" for source in retained)
    return AnswerOut(answer=answer, sources=retained, sufficient_evidence=True)
