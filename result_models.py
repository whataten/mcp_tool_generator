"""Execution result — see section 11 of docs/recordings_rule.md.

`error`, `screenshot_path` and `alerts_handled` are additions on top of the
documented shape; section 13 says executors ignore fields they do not know, so
extra detail here is safe for other consumers.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel


class StepLogEntry(BaseModel):
    step_id: str
    action: str
    status: Literal["success", "failed", "skipped"]
    duration_ms: Optional[int] = None
    note: Optional[str] = None


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
        "alert_open",
        "alert_not_found",
        "tab_not_found",
        "assertion_failed",
        "unsupported_action",
        "value_error",
        "unknown",
    ]
    attempted_selectors: Optional[list[dict]] = None
    screenshot_path: Optional[str] = None
    page_url_at_failure: Optional[str] = None


class ToolResult(BaseModel):
    scenario_id: str
    status: Literal["success", "failed", "partial"]
    started_at: str
    finished_at: str
    results: dict[str, Any] = {}
    failed_step: Optional[str] = None
    step_log: list[StepLogEntry] = []

    error: Optional[ErrorDetail] = None
    screenshot_path: Optional[str] = None
    # Text of any javascript dialogs that were closed automatically, in order.
    alerts_handled: list[str] = []
