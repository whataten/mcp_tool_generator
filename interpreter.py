import time

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoAlertPresentException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

import config
import selenium_runner as sr
from result_models import ErrorDetail, StepResult, ToolResult
from schema import Recording


def _classify_error(exc: Exception, step) -> ErrorDetail:
    if isinstance(exc, sr.TargetResolutionError):
        return ErrorDetail(
            step_id=step.id,
            action=step.action.value,
            message=str(exc),
            error_type="selector_not_found",
            attempted_selectors=[{"type": s.type.value, "value": s.value} for s in exc.selectors],
        )
    if isinstance(exc, sr.WindowNotFoundError):
        error_type = "window_not_found"
    elif isinstance(exc, sr.UnhandledAlertError):
        error_type = "alert_open"
    elif isinstance(exc, NoAlertPresentException):
        error_type = "alert_not_found"
    elif isinstance(exc, TimeoutException):
        error_type = "timeout"
    elif isinstance(exc, ElementClickInterceptedException):
        error_type = "click_intercepted"
    elif isinstance(exc, StaleElementReferenceException):
        error_type = "stale_element"
    elif isinstance(exc, WebDriverException):
        msg = str(exc).lower()
        if "chrome not reachable" in msg or "session deleted" in msg or "page crash" in msg:
            error_type = "page_crash"
        else:
            error_type = "webdriver_error"
    else:
        error_type = "unknown"

    return ErrorDetail(
        step_id=step.id,
        action=step.action.value,
        message=str(exc),
        error_type=error_type,
    )


class RecordingInterpreter:
    def __init__(self, recording: Recording, screenshot_dir: str = config.SCREENSHOTS_DIR):
        self.recording = recording
        self.screenshot_dir = screenshot_dir

    def run(self, bound_vars: dict) -> ToolResult:
        driver = sr.new_driver()
        step_results: list[StepResult] = []
        extracted: dict = {}
        alerts_handled: list[str] = []
        try:
            driver.get(self.recording.start_url)
            for step in self.recording.steps:
                try:
                    t0 = time.monotonic()
                    extra = sr.execute_step(driver, step, bound_vars, extracted, alerts_handled)
                    step_results.append(
                        StepResult(
                            step_id=step.id,
                            action=step.action.value,
                            status="ok",
                            duration_ms=int((time.monotonic() - t0) * 1000),
                        )
                    )
                    if extra:
                        extracted.update(extra)
                except Exception as e:
                    err = _classify_error(e, step)
                    err.screenshot_path = sr.capture_screenshot(
                        driver, self.screenshot_dir, self.recording.id, step.id
                    )
                    try:
                        err.page_url_at_failure = driver.current_url
                    except Exception:
                        pass
                    step_results.append(StepResult(step_id=step.id, action=step.action.value, status="error"))
                    return ToolResult(
                        status="error",
                        recording_id=self.recording.id,
                        step_results=step_results,
                        extracted=extracted,
                        error=err,
                        alerts_handled=alerts_handled,
                    )

            # The last step has usually just submitted something, so let the
            # browser land on the resulting page before capturing it.
            sr.wait_for_page_settled(driver)
            screenshot_path = sr.capture_screenshot(driver, self.screenshot_dir, self.recording.id, "final")
            return ToolResult(
                status="success",
                recording_id=self.recording.id,
                step_results=step_results,
                extracted=extracted,
                screenshot_path=screenshot_path,
                alerts_handled=alerts_handled,
            )
        finally:
            if not config.KEEP_BROWSER_OPEN:
                try:
                    driver.quit()
                except Exception:
                    pass
