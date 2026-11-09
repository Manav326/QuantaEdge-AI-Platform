from arq.connections import RedisSettings

from app.core.settings import get_settings
from app.services.ingestion import ingest_knowledge_document


async def ingest_document(ctx, document_id: str) -> None:
    await ingest_knowledge_document(document_id)


class WorkerSettings:
    functions = [ingest_document]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 1
    job_timeout = 900
    max_tries = 3
