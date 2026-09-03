import asyncio
import base64
import json
import os
from typing import Any, Optional

import mcp_types as types
from pydantic import BaseModel, Field, ValidationError, create_model

from interpreter import RecordingInterpreter
from schema import Recording, VarType

_TYPE_MAP = {
    VarType.STRING: str,
    VarType.NUMBER: float,
    VarType.BOOLEAN: bool,
    VarType.SECRET: str,
}


def build_input_model(recording: Recording) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for var_name, spec in recording.variables.items():
        py_type = _TYPE_MAP[spec.type]
        field_kwargs: dict[str, Any] = {"description": spec.description}
        if spec.type == VarType.SECRET:
            field_kwargs["json_schema_extra"] = {"format": "password"}
        if spec.required:
            fields[var_name] = (py_type, Field(..., **field_kwargs))
        else:
            fields[var_name] = (Optional[py_type], Field(spec.default, **field_kwargs))

    return create_model(f"{recording.id}__Input", **fields)


def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps({"error": message}, ensure_ascii=False))],
        isError=True,
    )


def _to_call_tool_result(result_json: dict, screenshot_path: Optional[str]) -> types.CallToolResult:
    content: list[Any] = [types.TextContent(type="text", text=json.dumps(result_json, ensure_ascii=False))]
    if screenshot_path and os.path.exists(screenshot_path):
        try:
            with open(screenshot_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            content.append(types.ImageContent(type="image", data=data, mimeType="image/png"))
        except OSError:
            pass
    return types.CallToolResult(content=content, isError=result_json.get("status") == "error")


class ToolRegistry:
    def __init__(self, recordings: dict[str, Recording]):
        self.recordings = recordings
        self.models: dict[str, type[BaseModel]] = {
            rid: build_input_model(r) for rid, r in recordings.items()
        }

    async def list_tools(self, ctx: Any, params: Any) -> types.ListToolsResult:
        tools = [
            types.Tool(
                name=r.id,
                description=f"{r.name} - {r.description}",
                inputSchema=self.models[r.id].model_json_schema(),
            )
            for r in self.recordings.values()
        ]
        return types.ListToolsResult(tools=tools)

    async def call_tool(self, ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        name = params.name
        arguments = params.arguments or {}

        recording = self.recordings.get(name)
        if recording is None:
            return _error_result(f"unknown tool '{name}'")

        model = self.models[name]
        try:
            validated = model.model_validate(arguments)
        except ValidationError as e:
            return _error_result(f"invalid arguments: {e}")
        bound_vars = validated.model_dump()

        interpreter = RecordingInterpreter(recording)
        result = await asyncio.to_thread(interpreter.run, bound_vars)
        result_json = result.model_dump(mode="json")
        screenshot_path = result.error.screenshot_path if result.error else result.screenshot_path
        return _to_call_tool_result(result_json, screenshot_path)
