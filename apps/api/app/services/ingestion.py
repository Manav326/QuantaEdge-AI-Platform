import uuid
from pathlib import Path

from sqlalchemy import delete, select

from app.core.layers import get_layers
from app.core.settings import get_settings
from app.db import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.providers.ollama import ProviderError
from app.services.chunking import chunk_pages
from app.services.extraction import extract_pages
from app.services.model_gateway import ModelGateway


async def ingest_knowledge_document(document_id: str) -> None:
    settings = get_settings()
    layers = get_layers()
    document_uuid = uuid.UUID(document_id)
    async with SessionLocal() as db:
        document = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == document_uuid))
        if document is None:
            return
        document.status = "processing"
        await db.commit()
        try:
            pages = extract_pages(Path(document.storage_path))
            chunk_settings = layers.layer("retrieval")["chunking"]
            chunks = chunk_pages(
                pages,
                int(chunk_settings.get("max_characters", 1800)),
                int(chunk_settings.get("overlap_characters", 240)),
            )
            if not chunks:
                raise ValueError("No extractable text was found")
            gateway = ModelGateway()
            batch_size = int(chunk_settings.get("embedding_batch_size", 16))
            embedded: list[tuple[object, list[float]]] = []
            for offset in range(0, len(chunks), batch_size):
                batch = chunks[offset:offset + batch_size]
                _, vectors, _ = await gateway.embed([item.content for item in batch])
                embedded.extend(zip(batch, vectors))
            await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_uuid))
            db.add_all([
                KnowledgeChunk(
                    document_id=document_uuid,
                    chunk_index=chunk.index,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    embedding=vector,
                )
                for chunk, vector in embedded
            ])
            document.chunk_count = len(embedded)
            document.status = "ready"
            document.error_code = None
            await db.commit()
        except (Exception, ProviderError):
            await db.rollback()
            current = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == document_uuid))
            if current is not None:
                current.status = "failed"
                current.error_code = "INGESTION_FAILED"
                await db.commit()
            raise
