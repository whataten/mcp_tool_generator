from typing import Any, Literal, Optional

from pydantic import BaseModel


class StepResult(BaseModel):
    step_id: str
    action: str
    status: Literal["ok", "error"]
    duration_ms: Optional[int] = None


class ErrorDetail(BaseModel):
    step_id: str
    action: str
    message: str
    error_type: Literal[
        "selector_not_found",
        "timeout",
        "click_intercepted",
        "stale_element",
        "page_crash",
        "webdriver_error",
        "invalid_arguments",
        "unknown",
    ]
    attempted_selectors: Optional[list[dict]] = None
    screenshot_path: Optional[str] = None
    page_url_at_failure: Optional[str] = None


class ToolResult(BaseModel):
    status: Literal["success", "error"]
    recording_id: str
    step_results: list[StepResult] = []
    extracted: dict[str, Any] = {}
    error: Optional[ErrorDetail] = None
