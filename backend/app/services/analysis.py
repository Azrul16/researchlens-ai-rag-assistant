import hashlib
import json

from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import AnalysisCache, Chunk, Document
from app.llm.factory import get_llm_provider
from app.rag.context import build_context, cited_sources, numbers_supported, validate_finding
from app.rag.prompts import MISSING, SYSTEM_PROMPT
from app.schemas_ai import (
    AnalysisOut,
    ComparisonOut,
    GeneratedComparison,
    PaperAnalysis,
    SummaryOut,
)


async def document_evidence(db, document, budget=None):
    """Cover sections before filling remaining space, and report incomplete coverage."""
    if document.processing_status != "ready":
        raise AppError(409, "DOCUMENT_NOT_READY", "This paper must finish processing first.")
    chunks = (
        await db.scalars(
            select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index)
        )
    ).all()
    # Cover each detected section and distribute remaining coverage across the paper.
    first, rest, seen = [], [], set()
    for chunk in chunks:
        section = chunk.section_title or f"page-{chunk.page_number}"
        if section not in seen:
            first.append(chunk)
            seen.add(section)
        else:
            rest.append(chunk)
    sources = [
        {
            "document_id": document.id,
            "document_title": document.title or document.original_filename,
            "page_number": chunk.page_number,
            "chunk_id": chunk.id,
            "section_title": chunk.section_title,
            "excerpt": chunk.content,
            "score": 1.0,
        }
        for chunk in [*first, *rest]
    ]
    context, retained = build_context(sources, budget)
    return context, retained, len(retained) == len(chunks)


def findings(analysis):
    return [
        analysis.research_problem,
        analysis.methodology,
        *analysis.objectives,
        *analysis.datasets,
        *analysis.models,
        *analysis.metrics,
        *analysis.key_results,
        *analysis.contributions,
        *analysis.limitations,
        *analysis.future_work,
    ]


async def analyze_document(db, document, refresh=False):
    settings = get_settings()
    model = settings.groq_model if settings.llm_provider == "groq" else settings.gemini_model
    fingerprint = hashlib.sha256(
        f"{document.file_hash}:{settings.llm_provider}:{model}:"
        f"{settings.context_token_budget}:analysis-v1".encode()
    ).hexdigest()
    cache = await db.scalar(select(AnalysisCache).where(AnalysisCache.document_id == document.id))
    if cache and cache.fingerprint == fingerprint and not refresh:
        return AnalysisOut.model_validate(cache.result)
    context, sources, complete = await document_evidence(db, document)
    if not sources:
        raise AppError(422, "NO_EVIDENCE", "No readable passages are available for this paper.")
    prompt = (
        SYSTEM_PROMPT + f"\nProduce a structured research analysis. Use '{MISSING}' with "
        "empty source_ids for unavailable single fields; empty lists for absent list fields. "
        "Every reported finding must carry source_ids. Do not infer absent information. "
        "The context may cover only part of the paper. Do not claim exhaustive coverage."
    )
    analysis = await get_llm_provider().generate_structured(
        prompt, [{"role": "user", "content": context}], PaperAnalysis
    )
    for finding in findings(analysis):
        validate_finding(finding, sources)
    # Deterministic document identity is authoritative, never model-invented metadata.
    analysis.title = document.title or document.original_filename
    analysis.authors = document.authors
    result = AnalysisOut(analysis=analysis, sources=sources, context_complete=complete)
    if cache:
        cache.result = result.model_dump()
        cache.fingerprint = fingerprint
    else:
        db.add(
            AnalysisCache(
                document_id=document.id, fingerprint=fingerprint, result=result.model_dump()
            )
        )
    await db.commit()
    return result


async def summarize_document(db, document, refresh=False):
    result = await analyze_document(db, document, refresh)
    analysis = result.analysis
    sections = [
        ("Research problem", [analysis.research_problem]),
        ("Objectives", analysis.objectives),
        ("Methodology", [analysis.methodology]),
        ("Datasets", analysis.datasets),
        ("Models / approaches", analysis.models),
        ("Evaluation metrics", analysis.metrics),
        ("Key results", analysis.key_results),
        ("Contributions", analysis.contributions),
        ("Limitations", analysis.limitations),
        ("Future work", analysis.future_work),
    ]
    text = f"# {analysis.title}\n\n"
    for heading, entries in sections:
        text += f"## {heading}\n"
        text += (
            "\n".join(
                "- " + finding.text + " " + " ".join(f"[{source}]" for source in finding.source_ids)
                for finding in entries
            )
            if entries
            else MISSING
        )
        text += "\n\n"
    return SummaryOut(
        summary=text, sources=result.sources, context_complete=result.context_complete
    )


async def compare_documents(db, workspace_id: str, document_ids: list[str], focus: str):
    documents = (await db.scalars(select(Document).where(Document.id.in_(document_ids)))).all()
    if len(documents) != len(document_ids) or any(
        d.workspace_id != workspace_id for d in documents
    ):
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Select papers from this workspace.")
    sources = []
    for document in documents:
        _, evidence, _ = await document_evidence(
            db, document, get_settings().context_token_budget // len(documents)
        )
        if not evidence:
            raise AppError(422, "NO_EVIDENCE", "One selected paper has no usable evidence.")
        sources.extend(evidence)
    context, sources = build_context(sources)
    prompt = (
        SYSTEM_PROMPT + "\nCompare every selected paper, with exactly one row per document_id. "
        "Use only sources belonging to that row's paper. Include source_ids for every row. "
        "Cite the narrative with [S1] identifiers. Mark comparable=false unless datasets, "
        "metrics and evaluation protocols clearly align. Never create a unified ranking "
        f"from incompatible metrics. Use '{MISSING}' for unsupported fields."
    )
    result = await get_llm_provider().generate_structured(
        prompt,
        [
            {
                "role": "user",
                "content": (
                    f"Focus: {focus}\nSelected document IDs: {json.dumps(document_ids)}\n{context}"
                ),
            }
        ],
        GeneratedComparison,
    )
    if len(result.rows) != len(document_ids) or {r.document_id for r in result.rows} != set(
        document_ids
    ):
        raise AppError(
            502, "INVALID_COMPARISON", "The provider omitted or invented a selected paper."
        )
    for row in result.rows:
        content = " ".join(
            str(value)
            for key, value in row.model_dump().items()
            if key not in {"document_id", "paper", "source_ids"}
        )
        row_sources = cited_sources(content, row.source_ids, sources)
        if row_sources is None or any(s["document_id"] != row.document_id for s in row_sources):
            raise AppError(
                502, "INVALID_COMPARISON", "Comparison citations do not match their paper."
            )
        row.paper = next(
            d.title or d.original_filename for d in documents if d.id == row.document_id
        )
        if not numbers_supported(content, row_sources):
            raise AppError(
                502, "INVALID_COMPARISON", "The comparison included unsupported numeric values."
            )
    narrative = "\n".join([result.narrative, *result.caveats])
    cited = cited_sources(narrative, result.source_ids, sources)
    if cited is None or not numbers_supported(narrative, cited):
        raise AppError(
            502, "INVALID_COMPARISON", "The narrative has unsupported citations or numbers."
        )
    if not result.comparable and not result.caveats:
        result.caveats.append(
            "Different experimental protocols may prevent direct numerical comparison."
        )
    return ComparisonOut(**result.model_dump(), sources=sources)
