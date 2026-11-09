from fastapi import APIRouter, Depends
from sqlalchemy import text
from redis.asyncio import Redis

from app.core.settings import get_settings
from app.db import SessionLocal
from app.providers.ollama import OllamaProvider
from app.security import ClientPrincipal, require_scope

router = APIRouter(tags=["operations"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "quantaedge-ai-platform"}


@router.get("/ready")
async def readiness(_: ClientPrincipal = Depends(require_scope("admin:read"))) -> dict:
    database_ok = False
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
            database_ok = True
    except Exception:
        database_ok = False
    redis_ok = False
    redis_client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=3)
    try:
        redis_ok = bool(await redis_client.ping())
    except Exception:
        redis_ok = False
    finally:
        await redis_client.aclose()
    provider_ok = await OllamaProvider().health()
    is_ready = database_ok and redis_ok and provider_ok
    return {
        "status": "ready" if is_ready else "degraded",
        "database": database_ok,
        "redis": redis_ok,
        "ollama": provider_ok,
        "environment": get_settings().environment,
    }
