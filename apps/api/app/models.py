import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_documents_curriculum_scope", "institution_ref", "curriculum", "course_id", "subject_id", "chapter_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    rights_status: Mapped[str] = mapped_column(String(32), nullable=False)
    rights_attested_by: Mapped[str] = mapped_column(String(160), nullable=False)
    institution_ref: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    curriculum: Mapped[str] = mapped_column(String(40), nullable=False)
    course_id: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(80), nullable=False)
    book_title: Mapped[str] = mapped_column(String(255), nullable=False)
    edition: Mapped[str | None] = mapped_column(String(120), nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    chapter_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(12), default="en", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_document_index"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class LearnerMemory(Base):
    __tablename__ = "learner_memories"
    __table_args__ = (
        Index("ix_learner_memories_scope", "institution_ref", "learner_ref", "is_active", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    learner_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    consent_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
