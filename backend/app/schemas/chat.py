"""Chat / AI assistant schemas."""
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None
    language: Optional[str] = None   # en | ta | auto
    include_profile: bool = False    # merge citizen profile if consented


class Citation(BaseModel):
    index: int
    title: str
    department: Optional[str] = None
    source_url: Optional[str] = None
    published_date: Optional[str] = None
    jurisdiction: Optional[str] = None
    verified_at: Optional[str] = None
    # Only 'official_verified' sources may be described as verified.
    verification_status: str = 'unverified'
    source_document_ref: Optional[str] = None


class DecisionLineageItem(BaseModel):
    step: str
    detail: Any
    timestamp: Optional[str] = None


class ChatResponse(BaseModel):
    message_id: UUID
    conversation_id: UUID
    answer: str
    intent: Optional[str] = None
    language: Optional[str] = None
    citations: List[Citation] = []
    trust_score: Optional[float] = None
    abstained: bool = False
    abstain_reason: Optional[str] = None
    decision_id: Optional[UUID] = None
    action_type: str = "inform"   # inform | guide | act
    suggested_actions: List[str] = []
    degraded: bool = False        # True if LLM unavailable
    contains_unverified: bool = False  # True if any cited source is not official_verified


class ConversationOut(BaseModel):
    conversation_id: UUID
    created_at: datetime
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    preview: Optional[str] = None

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    message_id: UUID
    role: str    # user | assistant
    content: str
    created_at: datetime
    citations: List[Citation] = []

    class Config:
        from_attributes = True
