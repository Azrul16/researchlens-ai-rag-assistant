from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import Chunk, Document, Workspace
from app.db.session import get_db
from app.schemas import ChunkOut, DocumentOut, WorkspaceInput, WorkspaceOut, WorkspacePatch
from app.services.documents import remove_document, upload_document
from app.services.vector_store import ensure_index, index_path, workspace_lock

router = APIRouter(prefix="/api/v1")
DB = Annotated[AsyncSession, Depends(get_db)]


async def require(db, model, resource_id):
    resource = await db.get(model, str(resource_id), populate_existing=True)
    if resource is None:
        raise AppError(404, "NOT_FOUND", "The requested resource does not exist.")
    return resource


@router.get("/health", tags=["health"])
async def health(db: DB):
    await db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "ok",
        "max_upload_mb": get_settings().max_upload_mb,
        "llm_provider": get_settings().llm_provider,
        "vector_store": "ok",
        "capabilities": ["workspaces", "pdf_extraction", "semantic_search", "rag", "analysis"],
        "llm_configured": bool(
            getattr(get_settings(), f"{get_settings().llm_provider}_api_key").get_secret_value()
        ),
    }


@router.get("/workspaces", response_model=list[WorkspaceOut], tags=["workspaces"])
async def list_workspaces(db: DB):
    return (await db.scalars(select(Workspace).order_by(Workspace.created_at.desc()))).all()


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201, tags=["workspaces"])
async def create_workspace(body: WorkspaceInput, db: DB):
    workspace = Workspace(**body.model_dump())
    db.add(workspace)
    await db.commit()
    return workspace


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut, tags=["workspaces"])
async def get_workspace(workspace_id: UUID, db: DB):
    return await require(db, Workspace, workspace_id)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceOut, tags=["workspaces"])
async def update_workspace(workspace_id: UUID, body: WorkspacePatch, db: DB):
    workspace = await require(db, Workspace, workspace_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(workspace, key, value)
    await db.commit()
    return workspace


@router.delete("/workspaces/{workspace_id}", status_code=204, tags=["workspaces"])
async def delete_workspace(workspace_id: UUID, db: DB):
    async with workspace_lock(str(workspace_id)):
        workspace = await require(db, Workspace, workspace_id)
        documents = (
            await db.scalars(select(Document).where(Document.workspace_id == workspace.id))
        ).all()
        paths = [Path(document.file_path) for document in documents]
        await db.delete(workspace)
        await db.commit()
        folder = index_path(str(workspace_id))
        (folder / "index.faiss").unlink(missing_ok=True)
        (folder / "metadata.json").unlink(missing_ok=True)
    for path in paths:
        path.unlink(missing_ok=True)


@router.get(
    "/workspaces/{workspace_id}/documents", response_model=list[DocumentOut], tags=["papers"]
)
async def list_documents(workspace_id: UUID, db: DB):
    await require(db, Workspace, workspace_id)
    return (
        await db.scalars(
            select(Document)
            .where(Document.workspace_id == str(workspace_id))
            .order_by(Document.created_at.desc())
        )
    ).all()


@router.post(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentOut,
    status_code=201,
    tags=["papers"],
)
async def upload(workspace_id: UUID, db: DB, file: UploadFile = File(...)):
    async with workspace_lock(str(workspace_id)):
        await require(db, Workspace, workspace_id)
        return await upload_document(db, str(workspace_id), file)


@router.get("/documents/{document_id}", response_model=DocumentOut, tags=["papers"])
async def get_document(document_id: UUID, db: DB):
    return await require(db, Document, document_id)


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkOut], tags=["papers"])
async def list_chunks(document_id: UUID, db: DB, offset: int = 0, limit: int = 50):
    await require(db, Document, document_id)
    if offset < 0 or not 1 <= limit <= 100:
        raise AppError(422, "INVALID_PAGINATION", "Use offset >= 0 and limit between 1 and 100.")
    return (
        await db.scalars(
            select(Chunk)
            .where(Chunk.document_id == str(document_id))
            .order_by(Chunk.chunk_index)
            .offset(offset)
            .limit(limit)
        )
    ).all()


@router.get("/documents/{document_id}/file", tags=["papers"])
async def download_document(document_id: UUID, db: DB):
    document = await require(db, Document, document_id)
    if not Path(document.file_path).is_file():
        raise AppError(404, "FILE_NOT_FOUND", "The source PDF is missing from storage.")
    return FileResponse(
        document.file_path,
        media_type="application/pdf",
        filename=document.original_filename,
        content_disposition_type="inline",
    )


@router.delete("/documents/{document_id}", status_code=204, tags=["papers"])
async def delete_document(document_id: UUID, db: DB):
    document = await require(db, Document, document_id)
    async with workspace_lock(document.workspace_id):
        document = await require(db, Document, document_id)
        await remove_document(db, document)


@router.post("/documents/{document_id}/retry", response_model=DocumentOut, tags=["papers"])
async def retry_document(document_id: UUID, db: DB):
    document = await require(db, Document, document_id)
    if document.chunk_count == 0:
        raise AppError(
            422, "NO_TEXT", "This document has no extractable text. Upload a text-based PDF."
        )
    async with workspace_lock(document.workspace_id):
        document = await require(db, Document, document_id)
        document.processing_status = "processing"
        await db.commit()
        await ensure_index(db, document.workspace_id, force=True)
    return document
