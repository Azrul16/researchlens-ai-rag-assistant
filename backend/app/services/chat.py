from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import Conversation, Message, now
from app.rag.pipeline import answer_question
from app.schemas_ai import ConversationDetail, MessageOut


def message_out(message):
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        sources=message.message_metadata.get("sources", []),
        created_at=message.created_at,
    )


async def conversation_detail(db, conversation_id: str):
    conversation = await db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    if conversation is None:
        raise AppError(404, "NOT_FOUND", "This conversation does not exist.")
    return ConversationDetail(
        **{
            key: getattr(conversation, key)
            for key in ("id", "workspace_id", "title", "created_at", "updated_at")
        },
        messages=[message_out(message) for message in conversation.messages],
    )


async def send_message(db, conversation, content: str, document_ids):
    """Commit a question and grounded response together; keep failures retryable."""
    count = get_settings().chat_history_messages
    messages = (
        (
            await db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(count)
            )
        ).all()
        if count
        else []
    )
    history = [{"role": message.role, "content": message.content} for message in reversed(messages)]
    result = await answer_question(db, conversation.workspace_id, content, history, document_ids)
    conversation = await db.get(Conversation, conversation.id, populate_existing=True)
    if conversation is None:
        raise AppError(
            404, "NOT_FOUND", "This conversation was deleted while the answer was generated."
        )
    db.add(Message(conversation_id=conversation.id, role="user", content=content))
    assistant = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        message_metadata={
            "sources": [s.model_dump() for s in result.sources],
            "sufficient_evidence": result.sufficient_evidence,
        },
    )
    db.add(assistant)
    if not messages:
        conversation.title = content[:120]
    conversation.updated_at = now()
    await db.commit()
    return result
