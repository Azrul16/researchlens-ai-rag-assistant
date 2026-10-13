from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.routes import DB, require
from app.api.search import validate_documents
from app.db.models import Conversation, Document, Workspace
from app.llm.factory import get_llm_provider
from app.schemas_ai import (
    AnalysisOut,
    AnswerOut,
    CompareInput,
    ComparisonOut,
    ConversationDetail,
    ConversationInput,
    ConversationOut,
    MessageInput,
    ProviderHealth,
    SummaryOut,
)
from app.services.analysis import analyze_document, compare_documents, summarize_document
from app.services.chat import conversation_detail, send_message
from app.services.vector_store import conversation_lock, workspace_lock

router = APIRouter(prefix="/api/v1", tags=["research"])


@router.get("/provider/health", response_model=ProviderHealth)
async def provider_health():
    return await get_llm_provider().health_check()


@router.post(
    "/workspaces/{workspace_id}/conversations", response_model=ConversationOut, status_code=201
)
async def create_conversation(workspace_id: UUID, body: ConversationInput, db: DB):
    await require(db, Workspace, workspace_id)
    conversation = Conversation(workspace_id=str(workspace_id), title=body.title)
    db.add(conversation)
    await db.commit()
    return conversation


@router.get("/workspaces/{workspace_id}/conversations", response_model=list[ConversationOut])
async def list_conversations(workspace_id: UUID, db: DB):
    await require(db, Workspace, workspace_id)
    return (
        await db.scalars(
            select(Conversation)
            .where(Conversation.workspace_id == str(workspace_id))
            .order_by(Conversation.updated_at.desc())
        )
    ).all()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: UUID, db: DB):
    return await conversation_detail(db, str(conversation_id))


@router.post("/conversations/{conversation_id}/messages", response_model=AnswerOut)
async def post_message(conversation_id: UUID, body: MessageInput, db: DB):
    async with conversation_lock(str(conversation_id)):
        conversation = await require(db, Conversation, conversation_id)
        await validate_documents(db, conversation.workspace_id, body.document_ids)
        return await send_message(
            db, conversation, body.content, [str(i) for i in body.document_ids]
        )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: UUID, db: DB):
    async with conversation_lock(str(conversation_id)):
        await db.delete(await require(db, Conversation, conversation_id))
        await db.commit()


@router.post("/documents/{document_id}/analyze", response_model=AnalysisOut)
async def analyze(document_id: UUID, db: DB, refresh: bool = False):
    document = await require(db, Document, document_id)
    async with workspace_lock(document.workspace_id):
        document = await require(db, Document, document_id)
        return await analyze_document(db, document, refresh)


@router.post("/documents/{document_id}/summary", response_model=SummaryOut)
async def summary(document_id: UUID, db: DB, refresh: bool = False):
    document = await require(db, Document, document_id)
    async with workspace_lock(document.workspace_id):
        document = await require(db, Document, document_id)
        return await summarize_document(db, document, refresh)


@router.post("/workspaces/{workspace_id}/compare", response_model=ComparisonOut)
async def compare(workspace_id: UUID, body: CompareInput, db: DB):
    async with workspace_lock(str(workspace_id)):
        await require(db, Workspace, workspace_id)
        return await compare_documents(
            db, str(workspace_id), [str(i) for i in body.document_ids], body.focus
        )
