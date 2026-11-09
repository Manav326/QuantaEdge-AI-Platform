import pytest
from pydantic import ValidationError

from app.compat_schemas import OpenAIChatCompletionRequest, OpenAIChatMessage


def test_compat_messages_accept_developer_and_tool_history():
    messages = [
        OpenAIChatMessage(role="developer", content="Be concise."),
        OpenAIChatMessage(role="assistant", content=None, tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {"name": "lookup", "arguments": "{\"query\":\"science\"}"},
        }]),
        OpenAIChatMessage(role="tool", tool_call_id="call_123", content="Found one result."),
        OpenAIChatMessage(role="assistant", content="Here is the result."),
    ]
    assert messages[0].role == "developer"
    assert messages[1].tool_calls[0]["function"]["name"] == "lookup"
    assert messages[2].tool_call_id == "call_123"


def test_compat_request_accepts_streaming_and_function_tools():
    payload = OpenAIChatCompletionRequest(
        model="qwen3.5-teacher-2b",
        stream=True,
        max_completion_tokens=256,
        messages=[{"role": "user", "content": "Find a file."}],
        tools=[{
            "type": "function",
            "function": {
                "name": "search_files",
                "description": "Search available files.",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        }],
        tool_choice="auto",
    )
    assert payload.stream is True
    assert payload.max_completion_tokens == 256
    assert payload.tools[0]["function"]["name"] == "search_files"


def test_tool_messages_require_tool_call_id():
    with pytest.raises(ValidationError):
        OpenAIChatMessage(role="tool", content="Done")


def test_assistant_message_requires_content_or_tool_calls():
    with pytest.raises(ValidationError):
        OpenAIChatMessage(role="assistant")


def test_only_single_choice_is_supported():
    with pytest.raises(ValidationError):
        OpenAIChatCompletionRequest(
            model="qwen3.5-teacher-2b",
            n=2,
            messages=[{"role": "user", "content": "Hello"}],
        )


def test_function_tool_choice_must_reference_a_declared_tool():
    with pytest.raises(ValidationError):
        OpenAIChatCompletionRequest(
            model="qwen3.5-teacher-2b",
            messages=[{"role": "user", "content": "Search."}],
            tools=[{
                "type": "function",
                "function": {"name": "search", "parameters": {"type": "object"}},
            }],
            tool_choice={"type": "function", "function": {"name": "read"}},
        )


def test_required_tool_choice_needs_tools():
    with pytest.raises(ValidationError):
        OpenAIChatCompletionRequest(
            model="qwen3.5-teacher-2b",
            messages=[{"role": "user", "content": "Search."}],
            tool_choice="required",
        )
