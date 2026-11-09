from app.compat_schemas import OpenAIChatCompletionRequest
from app.routers.openai_compat import (
    _inference_overrides,
    _normalise_tool_calls,
    _openai_usage,
    _selected_tools,
)


def test_openai_parameters_map_to_ollama_options():
    payload = OpenAIChatCompletionRequest(
        model="qwen3.5-teacher-2b",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.4,
        top_p=0.8,
        max_completion_tokens=320,
        seed=17,
        stop=["END"],
        response_format={"type": "json_object"},
    )
    options = _inference_overrides(payload)
    assert options == {
        "temperature": 0.4,
        "top_p": 0.8,
        "num_predict": 320,
        "stop": ["END"],
        "seed": 17,
        "format": "json",
    }


def test_tool_choice_can_disable_tools_or_select_one_function():
    tools = [
        {"type": "function", "function": {"name": "search"}},
        {"type": "function", "function": {"name": "read"}},
    ]
    disabled = OpenAIChatCompletionRequest(
        model="model", messages=[{"role": "user", "content": "Hi"}],
        tools=tools, tool_choice="none",
    )
    selected = OpenAIChatCompletionRequest(
        model="model", messages=[{"role": "user", "content": "Hi"}],
        tools=tools, tool_choice={"type": "function", "function": {"name": "read"}},
    )
    assert _selected_tools(disabled) is None
    assert [item["function"]["name"] for item in _selected_tools(selected)] == ["read"]


def test_ollama_tool_calls_are_normalised_to_openai_shape():
    calls = _normalise_tool_calls([{
        "function": {
            "name": "search",
            "arguments": {"query": "Class 6 science"},
        }
    }])
    assert calls[0]["type"] == "function"
    assert calls[0]["function"]["name"] == "search"
    assert calls[0]["function"]["arguments"] == '{"query":"Class 6 science"}'
    assert calls[0]["id"].startswith("call_")


def test_usage_always_includes_total_tokens():
    assert _openai_usage({"prompt_tokens": 11, "completion_tokens": 9}) == {
        "prompt_tokens": 11,
        "completion_tokens": 9,
        "total_tokens": 20,
    }
