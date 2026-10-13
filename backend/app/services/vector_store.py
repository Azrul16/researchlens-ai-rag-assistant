import hashlib
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

import faiss
import numpy as np
from filelock import FileLock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db.models import Chunk, Document
from app.services.embeddings import get_embedding_provider

logger = logging.getLogger(__name__)


@asynccontextmanager
async def conversation_lock(conversation_id: str):
    folder = get_settings().vector_index_dir / "conversation_locks"
    folder.mkdir(parents=True, exist_ok=True)
    lock = FileLock(folder / f"{UUID(conversation_id)}.lock", timeout=300, thread_local=False)
    await run_in_threadpool(lock.acquire)
    try:
        yield
    finally:
        await run_in_threadpool(lock.release)


def index_path(workspace_id: str) -> Path:
    return get_settings().vector_index_dir / str(UUID(workspace_id))


@asynccontextmanager
async def workspace_lock(workspace_id: str):
    """Serialize mutations and retrieval across local worker processes."""
    folder = index_path(workspace_id)
    folder.mkdir(parents=True, exist_ok=True)
    lock = FileLock(folder / "workspace.lock", timeout=300, thread_local=False)
    await run_in_threadpool(lock.acquire)
    try:
        yield
    finally:
        await run_in_threadpool(lock.release)


async def workspace_chunks(db: AsyncSession, workspace_id: str):
    return (
        await db.execute(
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(
                Chunk.workspace_id == workspace_id,
                Document.processing_status.in_(["extracted", "processing", "ready"]),
            )
            .order_by(Chunk.document_id, Chunk.chunk_index)
        )
    ).all()


def write_index(folder: Path, ids: list[str], vectors: np.ndarray, identity: str):
    """Atomically replace each file; checksum detects mismatched generations."""
    folder.mkdir(parents=True, exist_ok=True)
    temp_index = folder / f"{uuid4()}.tmp"
    temp_meta = folder / f"{uuid4()}.tmp"
    try:
        index = faiss.IndexFlatIP(vectors.shape[1])
        if len(vectors):
            index.add(vectors)
        faiss.write_index(index, str(temp_index))
        checksum = hashlib.sha256(temp_index.read_bytes()).hexdigest()
        temp_meta.write_text(
            json.dumps({"ids": ids, "identity": identity, "checksum": checksum}), encoding="utf-8"
        )
        os.replace(temp_index, folder / "index.faiss")
        os.replace(temp_meta, folder / "metadata.json")
        return index
    finally:
        temp_index.unlink(missing_ok=True)
        temp_meta.unlink(missing_ok=True)


def load_index(folder: Path, ids: list[str], identity: str):
    try:
        metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        raw = (folder / "index.faiss").read_bytes()
        if (
            metadata["ids"] != ids
            or metadata["identity"] != identity
            or metadata["checksum"] != hashlib.sha256(raw).hexdigest()
        ):
            return None
        index = faiss.read_index(str(folder / "index.faiss"))
        return index if index.ntotal == len(ids) else None
    except (OSError, ValueError, KeyError, RuntimeError):
        return None


async def ensure_index(db: AsyncSession, workspace_id: str, force: bool = False):
    """Recover indexes from authoritative chunks, including model changes."""
    started = time.perf_counter()
    rows = await workspace_chunks(db, workspace_id)
    provider = get_embedding_provider()
    ids = [chunk.id for chunk, _ in rows]
    index = (
        None
        if force
        else await run_in_threadpool(load_index, index_path(workspace_id), ids, provider.identity)
    )
    if index is None:
        vectors = await run_in_threadpool(
            provider.embed_documents, [chunk.content for chunk, _ in rows]
        )
        index = await run_in_threadpool(
            write_index, index_path(workspace_id), ids, vectors, provider.identity
        )
        for position, (chunk, document) in enumerate(rows):
            chunk.vector_position = position
            document.processing_status = "ready"
            document.processing_error = None
        await db.commit()
        logger.info(
            "index_rebuilt workspace_id=%s chunks=%s duration_ms=%.1f",
            workspace_id,
            len(ids),
            (time.perf_counter() - started) * 1000,
        )
    changed = False
    for position, (chunk, document) in enumerate(rows):
        if document.processing_status != "ready" or chunk.vector_position != position:
            document.processing_status = "ready"
            document.processing_error = None
            chunk.vector_position = position
            changed = True
    if changed:
        await db.commit()
    return index, rows


def search_index(index, vector, count):
    return index.search(np.ascontiguousarray([vector], dtype="float32"), count)


async def retrieve(
    db: AsyncSession,
    workspace_id: str,
    query: str,
    document_ids: list[str] | None = None,
    top_k: int | None = None,
    apply_threshold: bool = True,
):
    """Apply document filters before ranking; optionally rerank retained candidates."""
    settings = get_settings()
    async with workspace_lock(workspace_id):
        index, rows = await ensure_index(db, workspace_id)
        if not rows:
            return []
        vector = await run_in_threadpool(get_embedding_provider().embed_query, query)
        # Search all exact FlatIP rows so document filters cannot miss their best passages.
        scores, positions = await run_in_threadpool(search_index, index, vector, len(rows))
        matches = []
        for score, position in zip(scores[0], positions[0], strict=True):
            if position < 0:
                continue
            chunk, document = rows[int(position)]
            if document_ids and document.id not in document_ids:
                continue
            if (chunk.section_title or "").lower() == "references" and not any(
                term in query.lower() for term in ("reference", "citation", "bibliography")
            ):
                continue
            if apply_threshold and score < settings.retrieval_score_threshold:
                continue
            matches.append(
                {
                    "document_id": document.id,
                    "document_title": document.title or document.original_filename,
                    "page_number": chunk.page_number,
                    "chunk_id": chunk.id,
                    "section_title": chunk.section_title,
                    "excerpt": chunk.content,
                    "score": round(float(score), 6),
                }
            )
        matches = matches[: top_k or settings.retrieval_top_k]
    if settings.enable_reranker and matches:
        from app.services.reranking import rerank

        matches = await run_in_threadpool(rerank, query, matches)
    return matches
