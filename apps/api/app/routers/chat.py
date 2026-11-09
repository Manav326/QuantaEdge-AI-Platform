import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.layers import ConfigurationError, get_layers
from app.providers.ollama import ProviderError
from app.schemas import ChatCompletionRequest, ChatCompletionResponse
from app.security import ClientPrincipal, require_scope
from app.services.model_gateway import ModelGateway

router = APIRouter(prefix="/v1/chat", tags=["generation"])


@router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    payload: ChatCompletionRequest,
    _: ClientPrincipal = Depends(require_scope("chat")),
) -> ChatCompletionResponse:
    layers = get_layers()
    task = layers.task("general_chat")
    prompt_name = task.get("prompt", "general_assistant")
    messages = [{"role": "system", "content": layers.prompt(prompt_name)}]
    messages.extend(message.model_dump() for message in payload.messages)
    try:
        model_profile, content, usage = await ModelGateway().generate("general_chat", messages, payload.model)
    except ConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        model=model_profile,
        choices=[{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        usage=usage,
    )
