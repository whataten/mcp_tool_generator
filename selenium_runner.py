import os
import time
from typing import Any, Optional

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoAlertPresentException,
    NoSuchElementException,
    NoSuchWindowException,
    StaleElementReferenceException,
    UnexpectedAlertPresentException,
)
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

import config
from schema import ActionType, Selector, SelectorType, Step, Target

_BY_MAP = {
    SelectorType.CSS: By.CSS_SELECTOR,
    SelectorType.XPATH: By.XPATH,
}

_ACTION_CONDITION = {
    ActionType.INPUT: EC.element_to_be_clickable,
    ActionType.CLICK: EC.element_to_be_clickable,
    ActionType.SELECT: EC.element_to_be_clickable,
    ActionType.EXTRACT: EC.visibility_of_element_located,
    ActionType.WAIT: EC.visibility_of_element_located,
}


class TargetResolutionError(Exception):
    def __init__(self, selectors: list[Selector], timeout_ms: int):
        self.selectors = selectors
        self.timeout_ms = timeout_ms
        attempted = ", ".join(f"{s.type.value}={s.value!r}" for s in selectors)
        super().__init__(f"no selector matched within {timeout_ms}ms (tried: {attempted})")


class UnhandledAlertError(Exception):
    def __init__(self, text: str):
        self.alert_text = text
        super().__init__(f"a browser dialog is open (ALERT_ACTION=error): {text!r}")


def _prepare_options(options):
    if config.WINDOW_MODE == "headless":
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    if config.WINDOW_MODE == "background":
        # Park the window far off-screen: it never takes focus or covers what
        # the user is doing, but it still renders, so screenshots stay correct.
        options.add_argument("--window-position=-32000,-32000")

    # The W3C default is "dismiss and notify", which silently closes a dialog
    # and then fails the command that ran into it. "ignore" leaves the dialog
    # standing so handle_alert() decides what happens to it.
    options.set_capability("unhandledPromptBehavior", "ignore")

    if config.KEEP_BROWSER_OPEN:
        # Without this the browser dies with the driver process.
        options.add_experimental_option("detach", True)
    return options


def new_driver():
    if config.BROWSER == "edge":
        options = _prepare_options(webdriver.EdgeOptions())
        service = EdgeService(executable_path=config.DRIVER_PATH) if config.DRIVER_PATH else None
        return webdriver.Edge(options=options, service=service)

    options = _prepare_options(webdriver.ChromeOptions())
    service = ChromeService(executable_path=config.DRIVER_PATH) if config.DRIVER_PATH else None
    return webdriver.Chrome(options=options, service=service)


def handle_alert(driver, how: str, alert_input: Optional[str] = None) -> Optional[str]:
    """Close an open dialog and return its text, or None if none was open."""
    try:
        alert = driver.switch_to.alert
        text = alert.text
    except NoAlertPresentException:
        return None

    if alert_input is not None:
        try:
            alert.send_keys(alert_input)
        except Exception:
            pass

    if how == "dismiss":
        alert.dismiss()
    else:
        alert.accept()
    return text


def auto_handle_alert(driver) -> Optional[str]:
    """Close a dialog that appeared on its own, following config.ALERT_ACTION.

    A dialog blocks every other browser command, so this has to run before a
    step can do anything else.
    """
    try:
        text = driver.switch_to.alert.text
    except NoAlertPresentException:
        return None
    except NoSuchWindowException:
        # A popup that closed itself leaves the driver pointing at a dead
        # window; there is no dialog to worry about, and a switch_window step
        # is what puts things right.
        return None

    if config.ALERT_ACTION == "error":
        raise UnhandledAlertError(text)
    return handle_alert(driver, config.ALERT_ACTION)


def wait_for_page_settled(driver, timeout_ms: Optional[int] = None) -> None:
    """Wait for the document to finish loading, then let rendering catch up.

    The last step of a recording usually submits something, so without this the
    final screenshot catches the page that is on its way out.
    """
    limit = config.PAGE_SETTLE_TIMEOUT_MS if timeout_ms is None else timeout_ms
    deadline = time.monotonic() + limit / 1000
    while time.monotonic() < deadline:
        try:
            if driver.execute_script("return document.readyState") == "complete":
                break
        except UnexpectedAlertPresentException:
            auto_handle_alert(driver)
        except Exception:
            break
        time.sleep(config.POLL_INTERVAL_SECONDS)
    time.sleep(config.FINAL_SCREENSHOT_DELAY_MS / 1000)


def resolve_element(driver, target: Target, action: ActionType, timeout_ms: int):
    condition_factory = _ACTION_CONDITION[action]
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        for sel in target.selectors:
            locator = (_BY_MAP[sel.type], sel.value)
            try:
                result = condition_factory(locator)(driver)
                if result:
                    return result
            except (StaleElementReferenceException, NoSuchElementException):
                continue
        if time.monotonic() >= deadline:
            raise TargetResolutionError(target.selectors, timeout_ms)
        time.sleep(config.POLL_INTERVAL_SECONDS)


def timeout_for(step: Step) -> int:
    return step.wait_after.timeout_ms if step.wait_after else config.DEFAULT_TIMEOUT_MS


def resolve_value(value_source, bound_vars: dict, extracted: Optional[dict] = None) -> Any:
    if value_source.type == "literal":
        return value_source.value
    if value_source.type == "extracted":
        store = extracted or {}
        if value_source.name not in store:
            raise KeyError(
                f"extracted value '{value_source.name}' is not available yet "
                "(the step that reads it must run earlier)"
            )
        return store[value_source.name]
    return bound_vars[value_source.name]


def _stringify(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def do_input(driver, step: Step, bound_vars: dict, extracted: Optional[dict] = None) -> None:
    el = resolve_element(driver, step.target, ActionType.INPUT, timeout_for(step))
    el.clear()
    el.send_keys(_stringify(resolve_value(step.value, bound_vars, extracted)))


def do_click(driver, step: Step, bound_vars: dict) -> None:
    el = resolve_element(driver, step.target, ActionType.CLICK, timeout_for(step))
    try:
        el.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", el)


def do_select(driver, step: Step, bound_vars: dict, extracted: Optional[dict] = None) -> None:
    el = resolve_element(driver, step.target, ActionType.SELECT, timeout_for(step))
    select = Select(el)
    val = _stringify(resolve_value(step.value, bound_vars, extracted))
    try:
        select.select_by_value(val)
    except Exception:
        select.select_by_visible_text(val)


def do_navigate(driver, step: Step, bound_vars: dict, extracted: Optional[dict] = None) -> None:
    driver.get(str(resolve_value(step.value, bound_vars, extracted)))
    if step.target:
        resolve_element(driver, step.target, ActionType.EXTRACT, timeout_for(step))


def do_wait(driver, step: Step) -> None:
    if step.target:
        resolve_element(driver, step.target, ActionType.WAIT, timeout_for(step))
    else:
        time.sleep(timeout_for(step) / 1000)


def do_extract(driver, step: Step) -> dict[str, Any]:
    el = resolve_element(driver, step.target, ActionType.EXTRACT, timeout_for(step))
    val = el.get_attribute(step.extract_attribute) if step.extract_attribute else el.text
    return {step.extract_as: val}


def do_alert(driver, step: Step) -> Optional[dict[str, Any]]:
    """Wait for a dialog and close it. Fails if none shows up in time."""
    how = step.alert_action or "accept"
    limit = timeout_for(step)
    deadline = time.monotonic() + limit / 1000
    while True:
        text = handle_alert(driver, how, step.alert_input)
        if text is not None:
            return {step.extract_as: text} if step.extract_as else None
        if time.monotonic() >= deadline:
            raise NoAlertPresentException(
                f"step '{step.id}': expected a dialog within {limit}ms but none appeared"
            )
        time.sleep(config.POLL_INTERVAL_SECONDS)


class WindowNotFoundError(Exception):
    pass


def do_switch_window(driver, step: Step) -> None:
    """Move the driver to another browser window/tab.

    Clicking a button that opens a window does not move the driver — every
    later step would still act on the old window until this runs.
    """
    limit = timeout_for(step)
    deadline = time.monotonic() + limit / 1000
    target = step.window_target

    while True:
        handles = driver.window_handles

        if target == "original":
            driver.switch_to.window(handles[0])
            return

        if target == "new" and len(handles) > 1:
            driver.switch_to.window(handles[-1])
            return

        if target == "match":
            try:
                current = driver.current_window_handle
            except NoSuchWindowException:
                current = handles[0]
            for handle in handles:
                driver.switch_to.window(handle)
                if step.window_match in driver.current_url or step.window_match in driver.title:
                    return
            driver.switch_to.window(current)

        if time.monotonic() >= deadline:
            if target == "match":
                raise WindowNotFoundError(
                    f"step '{step.id}': no window with {step.window_match!r} in its URL or title "
                    f"appeared within {limit}ms"
                )
            raise WindowNotFoundError(
                f"step '{step.id}': no new window appeared within {limit}ms "
                f"(only {len(handles)} window open)"
            )
        time.sleep(config.POLL_INTERVAL_SECONDS)


def do_close_window(driver, step: Step) -> None:
    """Close the current window and go back to the one the recording started in."""
    handles = driver.window_handles
    if len(handles) <= 1:
        raise WindowNotFoundError(
            f"step '{step.id}': refusing to close the only open window"
        )
    driver.close()
    driver.switch_to.window(driver.window_handles[0])


def _dispatch_step(
    driver, step: Step, bound_vars: dict, extracted: Optional[dict] = None
) -> Optional[dict[str, Any]]:
    if step.action == ActionType.INPUT:
        do_input(driver, step, bound_vars, extracted)
    elif step.action == ActionType.CLICK:
        do_click(driver, step, bound_vars)
    elif step.action == ActionType.SELECT:
        do_select(driver, step, bound_vars, extracted)
    elif step.action == ActionType.NAVIGATE:
        do_navigate(driver, step, bound_vars, extracted)
    elif step.action == ActionType.WAIT:
        do_wait(driver, step)
    elif step.action == ActionType.EXTRACT:
        return do_extract(driver, step)
    elif step.action == ActionType.ALERT:
        return do_alert(driver, step)
    elif step.action == ActionType.SWITCH_WINDOW:
        do_switch_window(driver, step)
    elif step.action == ActionType.CLOSE_WINDOW:
        do_close_window(driver, step)
    else:
        raise ValueError(f"unsupported action: {step.action}")
    return None


def execute_step(
    driver,
    step: Step,
    bound_vars: dict,
    extracted: Optional[dict] = None,
    alerts_seen: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    def note(text: Optional[str]) -> None:
        if text is not None and alerts_seen is not None:
            alerts_seen.append(text)

    # An "alert" step wants to find the dialog itself; every other step has to
    # get it out of the way first, since it blocks all other browser commands.
    if step.action != ActionType.ALERT:
        note(auto_handle_alert(driver))

    try:
        return _dispatch_step(driver, step, bound_vars, extracted)
    except UnexpectedAlertPresentException:
        # A dialog opened partway through the step (a login notice, say).
        # Close it and give the step one more go.
        note(auto_handle_alert(driver))
        return _dispatch_step(driver, step, bound_vars, extracted)


def capture_screenshot(driver, screenshot_dir: str, recording_id: str, step_id: str) -> Optional[str]:
    try:
        os.makedirs(screenshot_dir, exist_ok=True)
        path = os.path.join(screenshot_dir, f"{recording_id}_{step_id}_{int(time.time())}.png")
        driver.save_screenshot(path)
        return path
    except Exception:
        return None
