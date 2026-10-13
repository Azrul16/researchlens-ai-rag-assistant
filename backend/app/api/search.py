from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.routes import DB, require
from app.core.errors import AppError
from app.db.models import Document, Workspace
from app.schemas_ai import SearchInput, SearchOut
from app.services.vector_store import ensure_index, retrieve, workspace_lock

router = APIRouter(prefix="/api/v1", tags=["search"])


async def validate_documents(db, workspace_id: str, ids):
    if not ids:
        return
    documents = (
        await db.scalars(select(Document).where(Document.id.in_([str(i) for i in ids])))
    ).all()
    if len(documents) != len(set(ids)) or any(d.workspace_id != workspace_id for d in documents):
        raise AppError(
            404, "DOCUMENT_NOT_FOUND", "Selected papers do not belong to this workspace."
        )
    if any(d.processing_status != "ready" for d in documents):
        raise AppError(
            409, "DOCUMENT_NOT_READY", "Wait for the selected papers to finish processing."
        )


@router.post("/workspaces/{workspace_id}/search", response_model=SearchOut)
async def semantic_search(workspace_id: UUID, body: SearchInput, db: DB):
    await require(db, Workspace, workspace_id)
    await validate_documents(db, str(workspace_id), body.document_ids)
    results = await retrieve(
        db, str(workspace_id), body.query, [str(i) for i in body.document_ids], body.top_k
    )
    return {"results": results}


@router.post("/workspaces/{workspace_id}/rebuild-index")
async def rebuild_index(workspace_id: UUID, db: DB):
    await require(db, Workspace, workspace_id)
    async with workspace_lock(str(workspace_id)):
        index, _ = await ensure_index(db, str(workspace_id), force=True)
    return {"status": "ok", "chunks": index.ntotal}
