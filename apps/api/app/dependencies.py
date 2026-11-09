from collections.abc import AsyncGenerator

from app.db import SessionLocal


async def get_db() -> AsyncGenerator:
    async with SessionLocal() as session:
        yield session
