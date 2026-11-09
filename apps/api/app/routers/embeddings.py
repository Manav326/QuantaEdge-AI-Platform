from fastapi import APIRouter, Depends, HTTPException

from app.core.layers import ConfigurationError, get_layers
from app.providers.ollama import ProviderError
from app.schemas import EmbeddingRequest, EmbeddingResponse
from app.security import ClientPrincipal, require_scope
from app.services.model_gateway import ModelGateway

router = APIRouter(prefix="/v1/embeddings", tags=["embeddings"])


@router.post("", response_model=EmbeddingResponse)
async def create_embeddings(
    payload: EmbeddingRequest,
    _: ClientPrincipal = Depends(require_scope("embeddings")),
) -> EmbeddingResponse:
    texts = [payload.input] if isinstance(payload.input, str) else payload.input
    if not texts or any(not item.strip() for item in texts):
        raise HTTPException(status_code=422, detail="Input text cannot be empty")
    try:
        profile, vectors, dimensions = await ModelGateway().embed(texts, payload.model)
    except ConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return EmbeddingResponse(
        model=profile,
        dimensions=dimensions,
        data=[{"object": "embedding", "index": index, "embedding": vector} for index, vector in enumerate(vectors)],
    )
