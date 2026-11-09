from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.settings import get_settings

REQUIRED_LAYERS = (
    "infrastructure.yaml",
    "providers.yaml",
    "models.yaml",
    "tasks.yaml",
    "retrieval.yaml",
    "curriculum.yaml",
    "security.yaml",
)


class ConfigurationError(RuntimeError):
    pass


class ConfigurationLayers:
    """Loads the versioned, layer-wise configuration tree once per process."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.layers: dict[str, dict[str, Any]] = {}
        for filename in REQUIRED_LAYERS:
            path = config_dir / filename
            if not path.is_file():
                raise ConfigurationError(f"Required configuration layer is missing: {filename}")
            parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(parsed, dict):
                raise ConfigurationError(f"Configuration layer must be a YAML object: {filename}")
            self.layers[filename.removesuffix(".yaml")] = parsed
        self._validate()

    def _validate(self) -> None:
        providers = self.layers["providers"].get("providers", {})
        models = self.layers["models"].get("models", {})
        tasks = self.layers["tasks"].get("tasks", {})
        if not providers or not models or not tasks:
            raise ConfigurationError("Providers, models and tasks layers must not be empty")
        for task_name, task in tasks.items():
            profile = task.get("model_profile")
            if profile and profile not in models:
                raise ConfigurationError(f"Task '{task_name}' references unknown model profile '{profile}'")
        for profile_name, profile in models.items():
            provider = profile.get("provider")
            if provider not in providers:
                raise ConfigurationError(f"Model profile '{profile_name}' references unknown provider '{provider}'")

    def layer(self, name: str) -> dict[str, Any]:
        return self.layers[name]

    def model(self, profile_name: str) -> dict[str, Any]:
        try:
            profile = self.layers["models"]["models"][profile_name]
        except KeyError as exc:
            raise ConfigurationError(f"Unknown model profile: {profile_name}") from exc
        if not profile.get("enabled", False):
            raise ConfigurationError(f"Model profile is disabled: {profile_name}")
        return profile

    def task(self, task_name: str) -> dict[str, Any]:
        try:
            return self.layers["tasks"]["tasks"][task_name]
        except KeyError as exc:
            raise ConfigurationError(f"Unknown task: {task_name}") from exc

    def task_model(self, task_name: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        task = self.task(task_name)
        profile_name = task.get("model_profile")
        if not profile_name:
            raise ConfigurationError(f"Task '{task_name}' does not define a model profile")
        profile = self.model(profile_name)
        provider = self.layers["providers"]["providers"][profile["provider"]]
        return profile_name, profile, provider

    def prompt(self, prompt_name: str) -> str:
        path = self.config_dir / "prompts" / f"{prompt_name}.md"
        if not path.is_file():
            raise ConfigurationError(f"Prompt file is missing: {prompt_name}")
        return path.read_text(encoding="utf-8").strip()


@lru_cache
def get_layers() -> ConfigurationLayers:
    return ConfigurationLayers(get_settings().config_dir)
