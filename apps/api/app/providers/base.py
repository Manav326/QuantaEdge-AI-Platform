from typing import Any, Protocol


class ModelProvider(Protocol):
    async def embed(self, model_id: str, texts: list[str], expected_dimensions: int) -> list[list[float]]: ...

    async def chat(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        parameters: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]: ...
