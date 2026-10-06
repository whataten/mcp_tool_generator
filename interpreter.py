"""Replays one recording and reports the result (section 11 of the rule doc)."""
import datetime
import time
from typing import Optional

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoAlertPresentException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

import config
import selenium_runner as sr
from result_models import ErrorDetail, StepLogEntry, ToolResult
from schema import Condition, Recording, Step


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat()


def _classify_error(exc: Exception, step: Step) -> ErrorDetail:
    if isinstance(exc, sr.TargetResolutionError):
        return ErrorDetail(
            step_id=step.id,
            action=step.action,
            message=str(exc),
            error_type="selector_not_found",
            attempted_selectors=[{"type": s.type.value, "value": s.value} for s in exc.selectors],
        )

    if isinstance(exc, sr.TabNotFoundError):
        error_type = "tab_not_found"
    elif isinstance(exc, sr.AssertionFailedError):
        error_type = "assertion_failed"
    elif isinstance(exc, sr.UnsupportedActionError):
        error_type = "unsupported_action"
    elif isinstance(exc, sr.UnhandledAlertError):
        error_type = "alert_open"
    elif isinstance(exc, NoAlertPresentException):
        error_type = "alert_not_found"
    elif isinstance(exc, (KeyError, ValueError)):
        error_type = "value_error"
    elif isinstance(exc, TimeoutException):
        error_type = "timeout"
    elif isinstance(exc, ElementClickInterceptedException):
        error_type = "click_intercepted"
    elif isinstance(exc, StaleElementReferenceException):
        error_type = "stale_element"
    elif isinstance(exc, WebDriverException):
        msg = str(exc).lower()
        if "not reachable" in msg or "session deleted" in msg or "page crash" in msg:
            error_type = "page_crash"
        else:
            error_type = "webdriver_error"
    else:
        error_type = "unknown"

    return ErrorDetail(
        step_id=step.id,
        action=step.action,
        message=str(exc),
        error_type=error_type,
    )


def _condition_holds(condition: Condition, bound_vars: dict, extracted: dict) -> bool:
    store = bound_vars if condition.source == "variable" else extracted
    present = condition.name in store
    if condition.op == "exists":
        return present
    if condition.op == "not_exists":
        return not present
    if not present:
        return False
    actual = store[condition.name]
    if condition.op == "equals":
        return actual == condition.value
    return str(condition.value) in str(actual)


class RecordingInterpreter:
    def __init__(self, recording: Recording, screenshot_dir: str = config.SCREENSHOTS_DIR):
        self.recording = recording
        self.screenshot_dir = screenshot_dir

    def run(self, bound_vars: dict) -> ToolResult:
        started_at = _now()
        driver = sr.new_driver()
        ctx = sr.ExecutionContext(driver)

        step_log: list[StepLogEntry] = []
        extracted: dict = {}
        alerts_handled: list[str] = []
        skipped_any = False

        try:
            driver.get(self.recording.start_url)
            ctx.root_handle = driver.current_window_handle

            for step in self.recording.steps:
                if step.is_annotation:
                    # Recorder bookkeeping, not an instruction (see schema.py).
                    step_log.append(
                        StepLogEntry(
                            step_id=step.id,
                            action=step.action,
                            status="skipped",
                            note="recorder annotation, nothing to replay",
                        )
                    )
                    continue

                if step.condition and not _condition_holds(step.condition, bound_vars, extracted):
                    step_log.append(
                        StepLogEntry(
                            step_id=step.id,
                            action=step.action,
                            status="skipped",
                            note="condition not met",
                        )
                    )
                    continue

                error = self._run_step(driver, step, bound_vars, extracted, ctx, alerts_handled, step_log)
                if error is None:
                    continue

                policy = step.on_error
                if policy and policy.strategy == "skip":
                    skipped_any = True
                    continue

                return self._failed(
                    started_at, step, error, extracted, step_log, alerts_handled
                )

            sr.wait_for_page_settled(driver)
            screenshot_path = sr.capture_screenshot(
                driver, self.screenshot_dir, self.recording.id, "final"
            )
            return ToolResult(
                scenario_id=self.recording.id,
                status="partial" if skipped_any else "success",
                started_at=started_at,
                finished_at=_now(),
                results=self._filter_outputs(extracted),
                failed_step=None,
                step_log=step_log,
                screenshot_path=screenshot_path,
                alerts_handled=alerts_handled,
            )
        except Exception as e:  # driver startup / start_url navigation failures
            synthetic = Step(id="__startup__", action="navigate", options={"url": self.recording.start_url})
            return self._failed(
                started_at, synthetic, _classify_error(e, synthetic), extracted, step_log, alerts_handled
            )
        finally:
            if not config.KEEP_BROWSER_OPEN:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _run_step(
        self, driver, step, bound_vars, extracted, ctx, alerts_handled, step_log
    ) -> Optional[ErrorDetail]:
        """Run one step, honouring its retry policy. Returns an error, or None."""
        policy = step.on_error
        attempts = 1 + (policy.retry_count if policy and policy.strategy == "retry" else 0)

        last_error: Optional[ErrorDetail] = None
        for attempt in range(attempts):
            t0 = time.monotonic()
            try:
                produced = sr.execute_step(driver, step, bound_vars, extracted, ctx, alerts_handled)
                if produced:
                    extracted.update(produced)
                step_log.append(
                    StepLogEntry(
                        step_id=step.id,
                        action=step.action,
                        status="success",
                        duration_ms=int((time.monotonic() - t0) * 1000),
                        note=f"succeeded on attempt {attempt + 1}" if attempt else None,
                    )
                )
                return None
            except Exception as e:
                last_error = _classify_error(e, step)
                if attempt + 1 < attempts:
                    time.sleep((policy.retry_interval_ms if policy else 1000) / 1000)

        last_error.screenshot_path = sr.capture_screenshot(
            driver, self.screenshot_dir, self.recording.id, step.id
        )
        try:
            last_error.page_url_at_failure = driver.current_url
        except Exception:
            pass

        note = None
        if policy and policy.strategy == "skip":
            note = "failed but skipped by on_error policy"
        step_log.append(
            StepLogEntry(step_id=step.id, action=step.action, status="failed", note=note)
        )
        return last_error

    def _failed(self, started_at, step, error, extracted, step_log, alerts_handled) -> ToolResult:
        return ToolResult(
            scenario_id=self.recording.id,
            status="failed",
            started_at=started_at,
            finished_at=_now(),
            results=self._filter_outputs(extracted),
            failed_step=step.id,
            step_log=step_log,
            error=error,
            screenshot_path=error.screenshot_path,
            alerts_handled=alerts_handled,
        )

    def _filter_outputs(self, extracted: dict) -> dict:
        if not self.recording.outputs:
            return dict(extracted)
        return {k: v for k, v in extracted.items() if k in self.recording.outputs}
