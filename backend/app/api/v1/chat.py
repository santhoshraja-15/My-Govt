"""AI Chat / Assistant API endpoints."""
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ConversationOut
from app.services.chat_service import ChatService
from app.security.dependencies import get_current_user_optional

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Send a message to MyGovt AI assistant and get a grounded response."""
    service = ChatService(db)
    try:
        response = await service.process_message(request, current_user)
        return response
    except Exception as e:
        logger.error("Chat processing error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process message")


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Get conversation history for the current user."""
    if not current_user:
        return []
    service = ChatService(db)
    return await service.get_conversations(current_user.user_id)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Get messages for a specific conversation."""
    service = ChatService(db)
    messages = await service.get_messages(conversation_id, current_user)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return messages


@router.get("/decisions/{decision_id}/lineage")
async def get_decision_lineage(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the 'Why this answer?' lineage for a specific decision."""
    service = ChatService(db)
    lineage = await service.get_decision_lineage(decision_id)
    if not lineage:
        raise HTTPException(status_code=404, detail="Decision not found")
    return lineage
