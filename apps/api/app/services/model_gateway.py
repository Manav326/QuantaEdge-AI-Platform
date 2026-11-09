from typing import Any

from app.core.settings import get_settings

from app.core.layers import ConfigurationError, get_layers
from app.providers.ollama import OllamaProvider


class ModelGateway:
    """Routes capabilities via logical profiles and task policies."""

    def __init__(self) -> None:
        self.layers = get_layers()

    def _provider(self, provider_config: dict[str, Any]):
        provider_type = provider_config.get("type")
        if provider_type == "ollama":
            env_name = provider_config.get("base_url_env", "OLLAMA_BASE_URL")
            settings = get_settings()
            # Resolve through Pydantic Settings so values from .env are honoured too.
            base_url = getattr(settings, env_name.lower(), None) or provider_config.get("default_base_url")
            return OllamaProvider(base_url)
        raise ConfigurationError(f"Unsupported provider type: {provider_type}")

    async def generate(self, task_name: str, messages: list[dict[str, str]], requested_profile: str | None = None):
        task = self.layers.task(task_name)
        profile_name = requested_profile or task.get("model_profile")
        profile = self.layers.model(profile_name)
        provider_config = self.layers.layer("providers")["providers"][profile["provider"]]
        if "chat" not in profile.get("capabilities", []):
            raise ConfigurationError(f"Model profile '{profile_name}' does not support chat")
        parameters = dict(task.get("parameters", {}))
        result, usage = await self._provider(provider_config).chat(profile["model_id"], messages, parameters)
        return profile_name, result, usage

    async def embed(self, texts: list[str], requested_profile: str | None = None):
        defaults = self.layers.layer("models").get("defaults", {})
        profile_name = requested_profile or defaults.get("embedding")
        profile = self.layers.model(profile_name)
        provider_config = self.layers.layer("providers")["providers"][profile["provider"]]
        if "embeddings" not in profile.get("capabilities", []):
            raise ConfigurationError(f"Model profile '{profile_name}' does not support embeddings")
        dimensions = int(profile.get("dimensions", 0))
        if dimensions < 1:
            raise ConfigurationError(f"Embedding profile '{profile_name}' has no valid dimensions")
        vectors = await self._provider(provider_config).embed(profile["model_id"], texts, dimensions)
        return profile_name, vectors, dimensions
