from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.layers import get_layers
from app.models import KnowledgeChunk, KnowledgeDocument


async def retrieve_curriculum_evidence(
    db: AsyncSession,
    query_vector: list[float],
    *,
    institution_ref: str | None,
    curriculum: str,
    course_id: str,
    subject_id: str,
    chapter_id: str | None,
) -> list[dict]:
    settings = get_layers().layer("retrieval")["search"]
    distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
    statement = (
        select(KnowledgeChunk, KnowledgeDocument, distance.label("distance"))
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeDocument.status == "ready",
            KnowledgeDocument.curriculum == curriculum,
            KnowledgeDocument.course_id == course_id,
            KnowledgeDocument.subject_id == subject_id,
        )
    )
    # Global curriculum sources are visible to all institutions; institution-owned
    # sources are visible only to the requesting institution.
    if institution_ref:
        statement = statement.where(
            or_(KnowledgeDocument.institution_ref.is_(None), KnowledgeDocument.institution_ref == institution_ref)
        )
    else:
        statement = statement.where(KnowledgeDocument.institution_ref.is_(None))
    if chapter_id:
        statement = statement.where(KnowledgeDocument.chapter_id == chapter_id)
    statement = statement.order_by(distance.asc()).limit(int(settings.get("top_k", 6)))
    result = await db.execute(statement)
    rows = result.all()
    output = []
    for chunk, document, raw_distance in rows:
        similarity = max(0.0, min(1.0, 1.0 - float(raw_distance)))
        if similarity < float(settings.get("minimum_similarity", 0.25)):
            continue
        output.append({
            "document_id": document.id,
            "institution_ref": document.institution_ref,
            "book_title": document.book_title,
            "edition": document.edition,
            "curriculum": document.curriculum,
            "course_id": document.course_id,
            "subject_id": document.subject_id,
            "chapter_id": document.chapter_id,
            "chapter_title": document.chapter_title,
            "page_number": chunk.page_number,
            "excerpt": chunk.content[:1200],
            "similarity": similarity,
        })
    return output
