from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=30000)


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    task: Literal["general_chat"] = "general_chat"
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int] | None = None


class EmbeddingRequest(BaseModel):
    model: str | None = None
    input: str | list[str] = Field(min_length=1)


class EmbeddingResponse(BaseModel):
    object: Literal["list"] = "list"
    model: str
    data: list[dict[str, Any]]
    dimensions: int


class LearningAnswerRequest(BaseModel):
    learner_ref: str | None = Field(default=None, max_length=160)
    institution_ref: str | None = Field(default=None, max_length=160)
    question: str = Field(min_length=2, max_length=12000)
    curriculum: str = Field(default="NCERT", max_length=40)
    course_id: str = Field(min_length=1, max_length=80)
    subject_id: str = Field(min_length=1, max_length=80)
    chapter_id: str | None = Field(default=None, max_length=80)
    language: str = Field(default="en", max_length=12)
    allow_general_knowledge: bool = False

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        return value.strip()


class Citation(BaseModel):
    document_id: UUID
    institution_ref: str | None = None
    book_title: str
    edition: str | None
    curriculum: str
    course_id: str
    subject_id: str
    chapter_id: str | None
    chapter_title: str | None
    page_number: int | None
    excerpt: str
    similarity: float


class LearningAnswerResponse(BaseModel):
    status: Literal["completed", "insufficient_evidence"]
    answer: str
    model: str | None
    citations: list[Citation]
    source_basis: Literal["authorised_curriculum_evidence", "general_model_knowledge", "none"]


class ModelProfile(BaseModel):
    id: str
    display_name: str
    provider: str
    capabilities: list[str]
    context_window: int | None = None
    dimensions: int | None = None
    quality_status: str


class DocumentStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    chunk_count: int
    error_code: str | None
    created_at: datetime


class RightsStatus:
    value: Literal["permission_granted", "owned_content", "public_domain", "pending_review", "unknown"]


class MemoryCreateRequest(BaseModel):
    institution_ref: str = Field(min_length=1, max_length=160)
    learner_ref: str = Field(min_length=1, max_length=160)
    memory_type: Literal["learning_preference", "mastered_concept", "misconception", "revision_need", "learning_goal"]
    content: str = Field(min_length=1, max_length=2000)
    source_ref: str | None = Field(default=None, max_length=160)
    consent_confirmed: bool
    consent_ref: str = Field(min_length=1, max_length=160)

    @field_validator("content")
    @classmethod
    def clean_memory_content(cls, value: str) -> str:
        return value.strip()


class MemoryRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_ref: str
    learner_ref: str
    memory_type: str
    content: str
    source_ref: str | None
    created_at: datetime
    updated_at: datetime
