import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.settings import get_settings
from app.routers import chat, embeddings, health, knowledge, learning, memories, models

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app = FastAPI(
    title="QuantaEdge AI Platform API",
    version="0.1.0",
    description="Standalone API-first AI service for QuantaEdge and authorised applications.",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None,
)
app.add_middleware(RequestIdMiddleware)
app.include_router(health.router)
app.include_router(models.router)
app.include_router(chat.router)
app.include_router(embeddings.router)
app.include_router(learning.router)
app.include_router(memories.router)
app.include_router(knowledge.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("qeai.api").exception("Unhandled request error", extra={"request_id": getattr(request.state, "request_id", None)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": getattr(request.state, "request_id", None)})
