import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.compat_schemas import OpenAIChatCompletionRequest, OpenAIModel, OpenAIModelList
from app.core.layers import ConfigurationError, get_layers
from app.providers.ollama import ProviderError
from app.security import ClientPrincipal, require_scope
from app.services.model_gateway import ModelGateway

router = APIRouter(prefix="/compat/v1", tags=["OpenAI-compatible API"])
logger = logging.getLogger("qeai.compat")


def _inference_overrides(payload: OpenAIChatCompletionRequest) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if payload.temperature is not None:
        overrides["temperature"] = payload.temperature
    if payload.top_p is not None:
        overrides["top_p"] = payload.top_p
    output_limit = payload.max_completion_tokens or payload.max_tokens
    if output_limit is not None:
        overrides["num_predict"] = output_limit
    if payload.stop is not None:
        overrides["stop"] = [payload.stop] if isinstance(payload.stop, str) else payload.stop
    if payload.seed is not None:
        overrides["seed"] = payload.seed
    if payload.response_format:
        format_type = payload.response_format.get("type")
        if format_type == "json_object":
            overrides["format"] = "json"
        elif format_type == "json_schema":
            schema = payload.response_format.get("json_schema", {}).get("schema")
            if isinstance(schema, dict):
                overrides["format"] = schema
    return overrides


def _selected_tools(payload: OpenAIChatCompletionRequest) -> list[dict[str, Any]] | None:
    tools = payload.tools
    if not tools or payload.tool_choice == "none":
        return None
    choice = payload.tool_choice
    if isinstance(choice, dict):
        function = choice.get("function") or {}
        selected_name = function.get("name")
        if selected_name:
            return [
                tool for tool in tools
                if (tool.get("function") or {}).get("name") == selected_name
            ]
    return tools


def _messages(payload: OpenAIChatCompletionRequest) -> list[dict[str, Any]]:
    layers = get_layers()
    system_prompt = layers.prompt("general_assistant")
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for item in payload.messages:
        message = item.model_dump(exclude_none=True)
        if message["role"] == "developer":
            message["role"] = "system"
        messages.append(message)
    return messages


def _normalise_tool_calls(raw_calls: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for raw in raw_calls or []:
        function = raw.get("function") or {}
        name = function.get("name")
        if not isinstance(name, str) or not name:
            continue
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
                arguments = parsed if isinstance(parsed, (dict, list)) else {}
            except json.JSONDecodeError:
                arguments = {}
        if not isinstance(arguments, (dict, list)):
            arguments = {}
        calls.append({
            "id": raw.get("id") or f"call_{uuid.uuid4().hex}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
            },
        })
    return calls


def _openai_usage(usage: dict[str, Any]) -> dict[str, int]:
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": int(usage.get("total_tokens") or prompt + completion),
    }


@router.get("/models", response_model=OpenAIModelList)
async def list_compatible_models(
    _: ClientPrincipal = Depends(require_scope("models:read")),
) -> OpenAIModelList:
    models = []
    for profile_id, item in get_layers().layer("models").get("models", {}).items():
        if item.get("enabled") and "chat" in item.get("capabilities", []):
            models.append(OpenAIModel(id=profile_id))
    return OpenAIModelList(data=models)


@router.post("/chat/completions")
async def create_chat_completion(
    payload: OpenAIChatCompletionRequest,
    _: ClientPrincipal = Depends(require_scope("chat")),
):
    gateway = ModelGateway()
    try:
        prepared = gateway.prepare_chat(
            "general_chat",
            payload.model,
            _inference_overrides(payload),
        )
        messages = _messages(payload)
        tools = _selected_tools(payload)
    except ConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile_name, _profile, provider, parameters = prepared
    if payload.stream:
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        return StreamingResponse(
            _stream_completion(
                provider=provider,
                model_id=_profile["model_id"],
                profile_name=profile_name,
                messages=messages,
                parameters=parameters,
                tools=tools,
                completion_id=completion_id,
                created=created,
                include_usage=bool((payload.stream_options or {}).get("include_usage")),
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        message, usage = await provider.chat_completion(
            _profile["model_id"],
            messages,
            parameters,
            tools=tools,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail="The configured model provider is unavailable") from exc

    tool_calls = _normalise_tool_calls(message.get("tool_calls"))
    response_message: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content") or "",
    }
    if tool_calls:
        response_message["tool_calls"] = tool_calls
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": profile_name,
        "choices": [{
            "index": 0,
            "message": response_message,
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }],
        "usage": _openai_usage(usage),
    }


async def _stream_completion(
    *,
    provider,
    model_id: str,
    profile_name: str,
    messages: list[dict[str, Any]],
    parameters: dict[str, Any],
    tools: list[dict[str, Any]] | None,
    completion_id: str,
    created: int,
    include_usage: bool,
) -> AsyncIterator[str]:
    def event(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"

    def chunk(delta: dict[str, Any], finish_reason: str | None = None) -> dict[str, Any]:
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": profile_name,
            "choices": [{
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }],
        }

    yield event(chunk({"role": "assistant"}))
    finish_reason = "stop"
    prompt_tokens = 0
    completion_tokens = 0
    try:
        async for item in provider.stream_chat_completion(
            model_id,
            messages,
            parameters,
            tools=tools,
        ):
            message = item.get("message") or {}
            content = message.get("content")
            if isinstance(content, str) and content:
                yield event(chunk({"content": content}))

            tool_calls = _normalise_tool_calls(message.get("tool_calls"))
            if tool_calls:
                finish_reason = "tool_calls"
                for index, call in enumerate(tool_calls):
                    yield event(chunk({
                        "tool_calls": [{
                            "index": index,
                            **call,
                        }]
                    }))

            if item.get("done"):
                prompt_tokens = int(item.get("prompt_eval_count") or 0)
                completion_tokens = int(item.get("eval_count") or 0)
    except ProviderError:
        logger.exception("Streaming completion failed")
        yield event({
            "error": {
                "message": "The configured model provider is unavailable",
                "type": "server_error",
                "code": "provider_error",
            }
        })
        yield "data: [DONE]\n\n"
        return

    yield event(chunk({}, finish_reason))
    if include_usage:
        yield event({
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": profile_name,
            "choices": [],
            "usage": _openai_usage({
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }),
        })
    yield "data: [DONE]\n\n"
