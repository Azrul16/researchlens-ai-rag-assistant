import hashlib
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import Chunk, Document
from app.services.pdf import parse_pdf
from app.services.vector_store import ensure_index

logger = logging.getLogger(__name__)


async def upload_document(db: AsyncSession, workspace_id: str, file: UploadFile) -> Document:
    """Bound upload memory, parse off the event loop, and persist safely."""
    settings = get_settings()
    if not (file.filename or "").lower().endswith(".pdf") or file.content_type not in {
        "application/pdf",
        "application/octet-stream",
    }:
        raise AppError(415, "UNSUPPORTED_FILE", "Only PDF files are supported.")
    payload = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(payload) > settings.max_upload_mb * 1024 * 1024:
        raise AppError(413, "FILE_TOO_LARGE", f"Maximum file size is {settings.max_upload_mb} MB.")
    digest = hashlib.sha256(payload).hexdigest()
    duplicate = await db.scalar(
        select(Document).where(Document.workspace_id == workspace_id, Document.file_hash == digest)
    )
    if duplicate:
        raise AppError(409, "DUPLICATE_DOCUMENT", "This PDF already exists in this workspace.")
    parsed = await run_in_threadpool(
        parse_pdf, payload, settings.chunk_size, settings.chunk_overlap
    )
    document_id = str(uuid4())
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / f"{document_id}.pdf"
    await run_in_threadpool(path.write_bytes, payload)
    document = Document(
        id=document_id,
        workspace_id=workspace_id,
        original_filename=Path(file.filename.replace("\\", "/")).name[:255],
        stored_filename=path.name,
        file_path=str(path),
        file_hash=digest,
        title=parsed["title"],
        abstract=parsed.get("abstract"),
        authors=parsed["authors"],
        page_count=parsed["page_count"],
        file_size=len(payload),
        chunk_count=0 if parsed["scanned"] else len(parsed["passages"]),
        processing_status="failed" if parsed["scanned"] else "extracted",
        processing_error=(
            "This document appears to be scanned or image-based. OCR is not currently enabled."
            if parsed["scanned"]
            else None
        ),
    )
    db.add(document)
    if not parsed["scanned"]:
        document.chunks = [
            Chunk(
                workspace_id=workspace_id,
                chunk_index=i,
                page_number=passage.page_number,
                section_title=passage.section_title,
                content=passage.content,
                token_count=passage.token_count,
            )
            for i, passage in enumerate(parsed["passages"])
        ]
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        path.unlink(missing_ok=True)
        raise AppError(
            409, "DUPLICATE_DOCUMENT", "This PDF already exists in this workspace."
        ) from exc
    except Exception:
        await db.rollback()
        path.unlink(missing_ok=True)
        raise
    logger.info("document_extracted document_id=%s workspace_id=%s", document_id, workspace_id)
    if not parsed["scanned"]:
        document.processing_status = "processing"
        await db.commit()
        try:
            await ensure_index(db, workspace_id, force=True)
        except Exception as exc:
            await db.rollback()
            document = await db.get(Document, document_id)
            document.processing_status = "failed"
            document.processing_error = (
                "Text was extracted, but embedding/indexing failed. Check the model cache "
                "and retry processing."
            )
            await db.commit()
            logger.error("indexing_failed document_id=%s type=%s", document_id, type(exc).__name__)
    return document


async def remove_document(db: AsyncSession, document: Document):
    """Remove stored passages and their source file."""
    path = Path(document.file_path)
    await db.delete(document)
    await db.commit()
    path.unlink(missing_ok=True)
    await ensure_index(db, document.workspace_id, force=True)
