import uuid
from pathlib import Path
from typing import Annotated

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.layers import get_layers
from app.core.settings import get_settings
from app.db import get_db
from app.models import KnowledgeDocument
from app.schemas import DocumentStatus
from app.security import ClientPrincipal, require_scope

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge ingestion"])
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}


@router.post("/documents", response_model=DocumentStatus, status_code=status.HTTP_202_ACCEPTED)
async def upload_knowledge_document(
    file: Annotated[UploadFile, File(...)],
    curriculum: Annotated[str, Form(min_length=2, max_length=40)],
    course_id: Annotated[str, Form(min_length=1, max_length=80)],
    subject_id: Annotated[str, Form(min_length=1, max_length=80)],
    book_title: Annotated[str, Form(min_length=2, max_length=255)],
    rights_status: Annotated[str, Form()],
    rights_attested_by: Annotated[str, Form(min_length=2, max_length=160)],
    institution_ref: Annotated[str | None, Form(max_length=160)] = None,
    language: Annotated[str, Form()] = "en",
    edition: Annotated[str | None, Form()] = None,
    publication_year: Annotated[int | None, Form()] = None,
    chapter_id: Annotated[str | None, Form()] = None,
    chapter_title: Annotated[str | None, Form()] = None,
    principal: ClientPrincipal = Depends(require_scope("knowledge:write")),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatus:
    layers = get_layers()
    allowed_rights = set(layers.layer("security")["knowledge_ingestion"]["required_rights_status"])
    if rights_status not in allowed_rights:
        raise HTTPException(status_code=403, detail="Source rights are not cleared for ingestion")
    settings = get_settings()
    original_name = Path((file.filename or "document").replace("\\", "/")).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Supported formats: PDF, DOCX, TXT, MD and CSV")
    max_bytes = int(layers.layer("infrastructure")["service"].get("max_upload_mb", 30)) * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded file is empty")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="The uploaded file exceeds the configured limit")

    upload_dir = settings.data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    document_id = uuid.uuid4()
    storage_path = upload_dir / f"{document_id}{suffix}"
    storage_path.write_bytes(content)
    document = KnowledgeDocument(
        id=document_id,
        source_filename=original_name[:255],
        storage_path=str(storage_path),
        content_type=file.content_type or "application/octet-stream",
        rights_status=rights_status,
        rights_attested_by=rights_attested_by.strip(),
        institution_ref=institution_ref.strip() if institution_ref and institution_ref.strip() else None,
        curriculum=curriculum.upper(),
        course_id=course_id.upper(),
        subject_id=subject_id.upper(),
        book_title=book_title.strip(),
        edition=edition,
        publication_year=publication_year,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        language=language,
        status="queued",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    queue = None
    try:
        queue = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await queue.enqueue_job("ingest_document", str(document.id))
    except Exception:
        document.status = "failed"
        document.error_code = "QUEUE_UNAVAILABLE"
        await db.commit()
        raise HTTPException(status_code=503, detail="The ingestion queue is unavailable") from None
    finally:
        if queue is not None:
            await queue.aclose()
    return DocumentStatus.model_validate(document)


@router.get("/documents/{document_id}", response_model=DocumentStatus)
async def get_document_status(
    document_id: uuid.UUID,
    _: ClientPrincipal = Depends(require_scope("knowledge:read")),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatus:
    document = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    return DocumentStatus.model_validate(document)
