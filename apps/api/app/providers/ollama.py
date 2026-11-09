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

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.is_success
        except httpx.HTTPError:
            return False
