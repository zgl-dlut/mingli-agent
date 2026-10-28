from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PersonaCreateRequest(BaseModel):
    person_id: int
    name: Optional[str] = Field(None, max_length=100)


class PersonaResponse(BaseModel):
    persona_id: int
    person_id: int
    name: str
    avatar_key: str
    profile: Dict[str, Any]
    prompt_version: str
    created_at: datetime


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=120)


class ConversationResponse(BaseModel):
    conversation_id: int
    persona_id: int
    title: str
    user_turn_count: int
    remaining_turns: int
    started_at: datetime
    last_message_at: datetime
    closed_at: Optional[datetime] = None
    rest_reminder_required: bool = False


class PersonaMessageResponse(BaseModel):
    message_id: int
    role: str
    content: str
    safety_category: Optional[str] = None
    created_at: datetime


class PersonaMessageListResponse(BaseModel):
    items: List[PersonaMessageResponse]
    conversation: ConversationResponse


class PersonaMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class PersonaMemoryResponse(BaseModel):
    enabled: bool
    preferred_name: Optional[str] = None
    current_context: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    important_relationships: List[Dict[str, str]] = Field(default_factory=list)
    stage_summary: str = ""
    updated_at: Optional[datetime] = None


class MemorySettingsRequest(BaseModel):
    enabled: bool
