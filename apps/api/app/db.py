from collections.abc import AsyncGenerator

from pgvector.asyncpg import register_vector
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.settings import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)


@event.listens_for(engine.sync_engine, "connect")
def register_pgvector(dbapi_connection, _connection_record) -> None:
    dbapi_connection.run_async(register_vector)


SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
