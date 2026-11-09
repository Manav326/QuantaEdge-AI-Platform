from pathlib import Path

from app.core.layers import ConfigurationLayers


def test_configuration_layers_load_and_resolve_tasks():
    root = Path(__file__).resolve().parents[3] / "config"
    layers = ConfigurationLayers(root)
    name, model, provider = layers.task_model("learning_answer")
    assert name == "qwen3.5-teacher-2b"
    assert model["model_id"] == "qwen3.5:2b-q4_K_M"
    assert provider["type"] == "ollama"
    assert model["dimensions"] if "dimensions" in model else True


def test_embedding_profile_is_1024_dimensions():
    root = Path(__file__).resolve().parents[3] / "config"
    layers = ConfigurationLayers(root)
    _, model, _ = layers.task_model("embedding")
    assert model["dimensions"] == 1024


def test_ollama_provider_defaults_to_windows_loopback():
    root = Path(__file__).resolve().parents[3] / "config"
    layers = ConfigurationLayers(root)
    provider = layers.layer("providers")["providers"]["ollama-local"]
    assert provider["default_base_url"] == "http://127.0.0.1:11434"
