from app.providers.ollama import OllamaProvider


def test_ollama_compat_maps_developer_and_tool_history():
    messages = OllamaProvider._normalise_messages([
        {"role": "developer", "content": "Be concise."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "search", "arguments": "{\"query\":\"test\"}"},
            }],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "Found it."},
    ])
    assert messages[0] == {"role": "system", "content": "Be concise."}
    assert messages[1]["tool_calls"][0]["function"]["arguments"] == {"query": "test"}
    assert messages[2] == {"role": "tool", "content": "Found it."}


def test_ollama_chat_payload_supports_tools_stream_and_json_mode():
    tool = {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search.",
            "parameters": {"type": "object", "properties": {}},
        },
    }
    payload = OllamaProvider._chat_payload(
        "qwen3.5:2b-q4_K_M",
        [{"role": "user", "content": "Search."}],
        {"temperature": 0.3, "num_predict": 100, "think": False, "format": "json"},
        [tool],
        stream=True,
    )
    assert payload["stream"] is True
    assert payload["think"] is False
    assert payload["options"] == {"temperature": 0.3, "num_predict": 100}
    assert payload["format"] == "json"
    assert payload["tools"] == [tool]
