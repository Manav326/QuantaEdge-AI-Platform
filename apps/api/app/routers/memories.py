import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import LearnerMemory
from app.schemas import MemoryCreateRequest, MemoryRecordResponse
from app.security import ClientPrincipal, require_scope

router = APIRouter(prefix="/v1/memories", tags=["learner memory"])


@router.post("", response_model=MemoryRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreateRequest,
    principal: ClientPrincipal = Depends(require_scope("memory:write")),
    db: AsyncSession = Depends(get_db),
) -> MemoryRecordResponse:
    if payload.consent_confirmed is not True:
        raise HTTPException(status_code=403, detail="Explicit learner consent is required before storing memory")
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Memory content cannot be empty")
    record = LearnerMemory(
        institution_ref=payload.institution_ref.strip(),
        learner_ref=payload.learner_ref.strip(),
        memory_type=payload.memory_type,
        content=content,
        source_ref=payload.source_ref,
        consent_ref=payload.consent_ref.strip(),
        is_active=True,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return MemoryRecordResponse.model_validate(record)


@router.get("", response_model=list[MemoryRecordResponse])
async def list_memories(
    institution_ref: Annotated[str, Query(min_length=1, max_length=160)],
    learner_ref: Annotated[str, Query(min_length=1, max_length=160)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    _: ClientPrincipal = Depends(require_scope("memory:read")),
    db: AsyncSession = Depends(get_db),
) -> list[MemoryRecordResponse]:
    statement = (
        select(LearnerMemory)
        .where(
            LearnerMemory.institution_ref == institution_ref,
            LearnerMemory.learner_ref == learner_ref,
            LearnerMemory.is_active.is_(True),
        )
        .order_by(LearnerMemory.updated_at.desc())
        .limit(limit)
    )
    records = (await db.scalars(statement)).all()
    return [MemoryRecordResponse.model_validate(record) for record in records]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    institution_ref: Annotated[str, Query(min_length=1, max_length=160)],
    learner_ref: Annotated[str, Query(min_length=1, max_length=160)],
    _: ClientPrincipal = Depends(require_scope("memory:delete")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    statement = delete(LearnerMemory).where(
        LearnerMemory.id == memory_id,
        LearnerMemory.institution_ref == institution_ref,
        LearnerMemory.learner_ref == learner_ref,
    )
    result = await db.execute(statement)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Learner memory not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
