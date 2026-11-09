from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OpenAIChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | None = Field(default=None, max_length=30000)
    name: str | None = Field(default=None, max_length=160)
    tool_call_id: str | None = Field(default=None, max_length=160)
    tool_calls: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def validate_message_content(self):
        if self.role in {"user", "system", "developer", "tool"} and self.content is None:
            raise ValueError(f"{self.role} messages require content")
        if self.role == "assistant" and self.content is None and not self.tool_calls:
            raise ValueError("assistant messages require content or tool_calls")
        if self.role == "tool" and not self.tool_call_id:
            raise ValueError("tool messages require tool_call_id")
        return self


class OpenAIChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = Field(min_length=1, max_length=160)
    messages: list[OpenAIChatMessage] = Field(min_length=1, max_length=80)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=32768)
    stop: str | list[str] | None = None
    seed: int | None = None
    n: Literal[1] = 1
    tools: list[dict[str, Any]] | None = Field(default=None, max_length=64)
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None
    response_format: dict[str, Any] | None = None
    stream_options: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_tools(self):
        if self.tool_choice not in (None, "none", "auto", "required") and not isinstance(self.tool_choice, dict):
            raise ValueError("tool_choice must be none, auto, required, or a function selector")
        tool_names = set()
        for tool in self.tools or []:
            if tool.get("type") != "function" or not isinstance(tool.get("function"), dict):
                raise ValueError("Only OpenAI function tools are supported")
            name = tool["function"].get("name")
            if not name:
                raise ValueError("Function tools require a name")
            tool_names.add(name)
        if self.tool_choice == "required" and not tool_names:
            raise ValueError("tool_choice=required needs at least one function tool")
        if isinstance(self.tool_choice, dict):
            function = self.tool_choice.get("function") or {}
            selected_name = function.get("name")
            if self.tool_choice.get("type") != "function" or not selected_name:
                raise ValueError("Function tool_choice requires type=function and function.name")
            if selected_name not in tool_names:
                raise ValueError("tool_choice references a function not present in tools")
        return self


class OpenAIModel(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "quantaedge"


class OpenAIModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[OpenAIModel]
