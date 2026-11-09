import json
from typing import Any

import httpx

from app.core.settings import get_settings


class ProviderError(RuntimeError):
    pass


class OllamaProvider:
    """Adapter to Ollama running natively on Windows, outside Docker."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or get_settings().ollama_base_url).rstrip("/")
        self.timeout = get_settings().api_request_timeout_seconds

    async def embed(self, model_id: str, texts: list[str], expected_dimensions: int) -> list[list[float]]:
        if not texts:
            return []
        payload = {"model": model_id, "input": texts, "truncate": True}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/embed", json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Embedding provider is unavailable or returned invalid data") from exc
        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ProviderError("Embedding provider returned an unexpected number of vectors")
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != expected_dimensions:
                actual = len(vector) if isinstance(vector, list) else "unknown"
                raise ProviderError(f"Embedding dimension mismatch: expected {expected_dimensions}, received {actual}")
        return vectors

    async def chat(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        parameters: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        payload = {
            "model": model_id,
            "messages": messages,
            "stream": False,
            "think": bool(parameters.get("think", False)),
            "options": {key: value for key, value in parameters.items() if key != "think"},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Generation provider is unavailable or returned invalid data") from exc
        message = data.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Generation provider returned an empty response")
        usage = {
            "prompt_tokens": int(data.get("prompt_eval_count") or 0),
            "completion_tokens": int(data.get("eval_count") or 0),
        }
        return content.strip(), usage

    @staticmethod
    def _normalise_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for source in messages:
            role = source.get("role", "user")
            if role == "developer":
                role = "system"
            item: dict[str, Any] = {"role": role}
            content = source.get("content")
            if content is not None:
                item["content"] = content
            elif role == "assistant":
                item["content"] = ""
            name = source.get("name")
            if name:
                item["name"] = name
            tool_calls = source.get("tool_calls")
            if role == "assistant" and tool_calls:
                normalized_calls = []
                for call in tool_calls:
                    function = call.get("function") or {}
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {}
                    if not isinstance(arguments, (dict, list)):
                        arguments = {}
                    normalized_calls.append({
                        "function": {
                            "name": function.get("name", ""),
                            "arguments": arguments,
                        }
                    })
                item["tool_calls"] = normalized_calls
            # Ollama correlates tool results by their order in the message history.
            # OpenAI tool_call_id is intentionally omitted from the provider payload.
            normalized.append(item)
        return normalized

    @staticmethod
    def _chat_payload(
        model_id: str,
        messages: list[dict[str, Any]],
        parameters: dict[str, Any],
        tools: list[dict[str, Any]] | None,
        stream: bool,
    ) -> dict[str, Any]:
        think = bool(parameters.get("think", False))
        options = {key: value for key, value in parameters.items() if key not in {"think", "format"}}
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": OllamaProvider._normalise_messages(messages),
            "stream": stream,
            "think": think,
            "options": options,
        }
        if tools:
            payload["tools"] = tools
        if parameters.get("format") is not None:
            payload["format"] = parameters["format"]
        return payload

    @staticmethod
    def _usage(data: dict[str, Any]) -> dict[str, int]:
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    async def chat_completion(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        parameters: dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        payload = self._chat_payload(model_id, messages, parameters, tools, stream=False)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Generation provider is unavailable or returned invalid data") from exc

        message = data.get("message") or {}
        content = message.get("content")
        raw_calls = message.get("tool_calls") or []
        if not isinstance(content, str):
            content = ""
        if not content.strip() and not raw_calls:
            raise ProviderError("Generation provider returned an empty response")
        result: dict[str, Any] = {"role": "assistant", "content": content}
        if raw_calls:
            result["tool_calls"] = raw_calls
        return result, self._usage(data)

    async def stream_chat_completion(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        parameters: dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
    ):
        payload = self._chat_payload(model_id, messages, parameters, tools, stream=True)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise ProviderError("Generation provider returned invalid streaming data") from exc
                        if not isinstance(item, dict):
                            raise ProviderError("Generation provider returned invalid streaming data")
                        yield item
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Generation provider is unavailable or returned invalid data") from exc

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.is_success
        except httpx.HTTPError:
            return False
