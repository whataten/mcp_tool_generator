"""Selenium side of the executor: driver setup, element lookup, action catalog.

Action behaviour follows sections 7-10 of docs/recordings_rule.md.
"""
import datetime
import os
import random
import re
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
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

import config
from schema import ActionType, Selector, SelectorType, Step, Target, WaitUntil


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


class TabNotFoundError(Exception):
    pass


class AssertionFailedError(Exception):
    pass


class UnsupportedActionError(Exception):
    pass


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# dialogs (section 9)
# --------------------------------------------------------------------------
def handle_alert(driver, how: str, alert_input: Optional[str] = None) -> Optional[str]:
    """Close an open dialog and return its text, or None if none was open."""
    try:
        alert = driver.switch_to.alert
        text = alert.text
    except (NoAlertPresentException, NoSuchWindowException):
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
        # window; there is no dialog to worry about, and a switch_tab step is
        # what puts things right.
        return None

    if config.ALERT_ACTION == "error":
        raise UnhandledAlertError(text)
    return handle_alert(driver, config.ALERT_ACTION)


# --------------------------------------------------------------------------
# selectors (section 4)
# --------------------------------------------------------------------------
def _xpath_literal(value: str) -> str:
    """Quote a string for XPath, including values containing both quote kinds."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"


def _locator_for(sel: Selector) -> tuple[str, str]:
    if sel.type == SelectorType.CSS:
        return (By.CSS_SELECTOR, sel.value)
    if sel.type == SelectorType.XPATH:
        return (By.XPATH, sel.value)
    if sel.type == SelectorType.TEST_ID:
        return (By.CSS_SELECTOR, f'[data-testid="{sel.value}"], [data-test-id="{sel.value}"]')
    if sel.type == SelectorType.ARIA_LABEL:
        lit = _xpath_literal(sel.value)
        if sel.exact:
            return (By.XPATH, f"//*[@aria-label={lit}]")
        return (By.XPATH, f"//*[contains(@aria-label, {lit})]")
    if sel.type == SelectorType.PLACEHOLDER:
        lit = _xpath_literal(sel.value)
        if sel.exact:
            return (By.XPATH, f"//*[@placeholder={lit}]")
        return (By.XPATH, f"//*[contains(@placeholder, {lit})]")
    if sel.type == SelectorType.TEXT:
        lit = _xpath_literal(sel.value)
        if sel.exact:
            return (By.XPATH, f"//*[normalize-space(text())={lit}]")
        return (By.XPATH, f"//*[contains(normalize-space(text()), {lit})]")
    if sel.type == SelectorType.ROLE:
        # Explicit role attribute, plus the handful of implicit roles that come
        # up most often in recordings.
        implicit = {
            "button": "button, input[type='button'], input[type='submit']",
            "link": "a[href]",
            "textbox": "input[type='text'], input:not([type]), textarea",
            "checkbox": "input[type='checkbox']",
            "radio": "input[type='radio']",
            "combobox": "select",
        }.get(sel.value, "")
        css = f'[role="{sel.value}"]'
        return (By.CSS_SELECTOR, f"{css}, {implicit}" if implicit else css)
    raise ValueError(f"unsupported selector type: {sel.type}")


def _matches_role_name(element, sel: Selector) -> bool:
    if sel.type != SelectorType.ROLE or not sel.role_name:
        return True
    name = (element.get_attribute("aria-label") or element.text or "").strip()
    return sel.role_name in name if not sel.exact else sel.role_name == name


def enter_frames(driver, frames: list[Selector]) -> None:
    """Move into a chain of iframes, starting from the top document."""
    driver.switch_to.default_content()
    for frame_sel in frames:
        by, value = _locator_for(frame_sel)
        driver.switch_to.frame(driver.find_element(by, value))


def resolve_element(
    driver,
    target: Target,
    timeout_ms: Optional[int] = None,
    *,
    require_visible: bool = True,
    frame_context: Optional[list[Selector]] = None,
):
    """Find an element, trying each selector in order until one matches."""
    limit = config.DEFAULT_TIMEOUT_MS if timeout_ms is None else timeout_ms
    deadline = time.monotonic() + limit / 1000
    frames = target.frame_path or frame_context or []

    while True:
        if frames:
            try:
                enter_frames(driver, frames)
            except Exception:
                pass
        for sel in target.selectors:
            try:
                by, value = _locator_for(sel)
                matches = driver.find_elements(by, value)
                if sel.type == SelectorType.ROLE and sel.role_name:
                    matches = [m for m in matches if _matches_role_name(m, sel)]
                if require_visible:
                    matches = [m for m in matches if m.is_displayed()]
                if len(matches) > target.nth:
                    found = matches[target.nth]
                    if target.scroll_into_view:
                        try:
                            driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'center'});", found
                            )
                        except Exception:
                            pass
                    return found
            except (StaleElementReferenceException, NoSuchElementException):
                continue
        if time.monotonic() >= deadline:
            raise TargetResolutionError(target.selectors, limit)
        time.sleep(config.POLL_INTERVAL_SECONDS)


# --------------------------------------------------------------------------
# values (section 5)
# --------------------------------------------------------------------------
_EXPR_CALL = re.compile(r"^(\w+)\((.*)\)$")


def _eval_expression(expr: str) -> Any:
    """Evaluate one of the whitelisted expression forms.

    Deliberately not a general evaluator — section 5 limits this to a fixed set
    of safe functions, so recordings can never smuggle in arbitrary code.
    """
    parts = [p.strip() for p in _split_top_level(expr, "+")]
    rendered = [str(_eval_expression_atom(p)) for p in parts]
    if len(rendered) == 1:
        return _eval_expression_atom(parts[0])
    return "".join(rendered)


def _split_top_level(expr: str, sep: str) -> list[str]:
    out, depth, current, quote = [], 0, "", None
    for ch in expr:
        if quote:
            current += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            current += ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(current)
            current = ""
            continue
        current += ch
    out.append(current)
    return out


def _eval_expression_atom(atom: str) -> Any:
    atom = atom.strip()
    if (atom.startswith("'") and atom.endswith("'")) or (
        atom.startswith('"') and atom.endswith('"')
    ):
        return atom[1:-1]
    if re.fullmatch(r"-?\d+", atom):
        return int(atom)
    if re.fullmatch(r"-?\d*\.\d+", atom):
        return float(atom)

    call = _EXPR_CALL.match(atom)
    if not call:
        raise ValueError(f"unsupported expression: {atom!r}")
    func, raw_args = call.group(1), call.group(2).strip()
    args = [_eval_expression_atom(a) for a in _split_top_level(raw_args, ",")] if raw_args else []

    if func == "today":
        fmt = args[0] if args else "%Y-%m-%d"
        return datetime.date.today().strftime(fmt)
    if func == "now":
        fmt = args[0] if args else "%Y-%m-%d %H:%M:%S"
        return datetime.datetime.now().strftime(fmt)
    if func == "concat":
        return "".join(str(a) for a in args)
    if func == "random_int":
        low, high = (int(args[0]), int(args[1])) if len(args) >= 2 else (0, 2**31 - 1)
        return random.randint(low, high)
    raise ValueError(f"unsupported expression function: {func}()")


def resolve_value(value_source, bound_vars: dict, extracted: Optional[dict] = None) -> Any:
    if value_source.type == "literal":
        return value_source.value
    if value_source.type == "expression":
        return _eval_expression(str(value_source.value))
    if value_source.type == "extracted_ref":
        store = extracted or {}
        if value_source.name not in store:
            raise KeyError(
                f"extracted value '{value_source.name}' is not available yet "
                "(the step that reads it must run earlier)"
            )
        return store[value_source.name]
    if value_source.name not in bound_vars:
        raise KeyError(f"variable '{value_source.name}' was not supplied")
    return bound_vars[value_source.name]


def _stringify(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# --------------------------------------------------------------------------
# waits (section 6)
# --------------------------------------------------------------------------
def _document_ready(driver, states: tuple[str, ...]) -> Optional[bool]:
    """True/False for the ready state, or None when a dialog is in the way.

    Waits must never close a dialog themselves: an explicit `alert` step may be
    coming up to handle it, and swallowing it here would leave that step with
    nothing to find. Nothing on the page can progress while a dialog is open,
    so None means "stop waiting and let the next step deal with it".
    """
    try:
        return driver.execute_script("return document.readyState") in states
    except UnexpectedAlertPresentException:
        return None
    except Exception:
        return True


def perform_wait(driver, wait, ctx=None) -> None:
    """Apply a Wait object (section 6)."""
    if wait is None:
        return
    limit = wait.timeout_ms
    deadline = time.monotonic() + limit / 1000
    until = wait.wait_until

    if until == WaitUntil.FIXED_DELAY:
        if config.FIXED_DELAY_MODE == "sleep":
            time.sleep(limit / 1000)
            return
        # "settle" (default): treat timeout_ms as an upper bound and move on
        # once the page is done loading. A recording with 3s after every step
        # would otherwise spend most of its time asleep.
        while time.monotonic() < deadline:
            ready = _document_ready(driver, ("complete",))
            if ready is None:
                return  # dialog open; the next step handles it
            if ready:
                break
            time.sleep(config.POLL_INTERVAL_SECONDS)
        time.sleep(min(config.SETTLE_DELAY_MS, limit) / 1000)
        return

    if until in (WaitUntil.SELECTOR_VISIBLE, WaitUntil.SELECTOR_HIDDEN):
        want_visible = until == WaitUntil.SELECTOR_VISIBLE
        target = wait.target
        if target is None:
            return
        while True:
            visible = True
            try:
                resolve_element(
                    driver,
                    target,
                    timeout_ms=int(config.POLL_INTERVAL_SECONDS * 1000),
                    frame_context=ctx.frame_stack if ctx else None,
                )
            except TargetResolutionError:
                visible = False
            if visible == want_visible:
                return
            if time.monotonic() >= deadline:
                state = "visible" if want_visible else "hidden"
                raise TargetResolutionError(target.selectors, limit) if want_visible else TimeoutError(
                    f"element did not become {state} within {limit}ms"
                )
            time.sleep(config.POLL_INTERVAL_SECONDS)

    if until in (WaitUntil.LOAD, WaitUntil.NETWORK_IDLE):
        while time.monotonic() < deadline:
            ready = _document_ready(driver, ("complete",))
            if ready is None:
                return
            if ready:
                break
            time.sleep(config.POLL_INTERVAL_SECONDS)
        if until == WaitUntil.NETWORK_IDLE:
            # No CDP here, so approximate: once loading is done, give late XHR
            # work a brief quiet period.
            time.sleep(min(config.SETTLE_DELAY_MS, limit) / 1000)
        return

    if until == WaitUntil.DOM_CONTENT_LOADED:
        while time.monotonic() < deadline:
            ready = _document_ready(driver, ("interactive", "complete"))
            if ready is None or ready:
                return
            time.sleep(config.POLL_INTERVAL_SECONDS)
        return

    if until == WaitUntil.DIALOG_PRESENT:
        while time.monotonic() < deadline:
            try:
                driver.switch_to.alert.text
                return
            except (NoAlertPresentException, NoSuchWindowException):
                time.sleep(config.POLL_INTERVAL_SECONDS)
        raise NoAlertPresentException(f"no dialog appeared within {limit}ms")


def wait_for_page_settled(driver, timeout_ms: Optional[int] = None) -> None:
    """Wait for the document to finish loading, then let rendering catch up.

    The last step of a recording usually submits something, so without this the
    final screenshot catches the page that is on its way out.
    """
    limit = config.PAGE_SETTLE_TIMEOUT_MS if timeout_ms is None else timeout_ms
    deadline = time.monotonic() + limit / 1000
    while time.monotonic() < deadline:
        ready = _document_ready(driver, ("complete",))
        if ready is None:
            return  # a dialog is up; capture it as it stands
        if ready:
            break
        time.sleep(config.POLL_INTERVAL_SECONDS)
    time.sleep(config.FINAL_SCREENSHOT_DELAY_MS / 1000)


# --------------------------------------------------------------------------
# execution context
# --------------------------------------------------------------------------
class ExecutionContext:
    """State that outlives a single step: open tabs and the current iframe."""

    def __init__(self, driver):
        self.driver = driver
        self.frame_stack: list[Selector] = []
        # name given by a step's extract_as -> window handle
        self.tabs: dict[str, str] = {}
        # window handle -> the handle that was active when it appeared
        self.openers: dict[str, str] = {}
        self.root_handle = driver.current_window_handle

    def bound_handles(self) -> set[str]:
        return set(self.tabs.values()) | {self.root_handle}

    def register_tab(self, name: Optional[str], handle: str, opener: Optional[str]) -> None:
        if name:
            self.tabs[name] = handle
        if opener:
            self.openers[handle] = opener

    def resolve_tab_ref(self, tab_ref: Any) -> str:
        """Turn options.tab_ref into a window handle (section 7)."""
        handles = self.driver.window_handles

        if isinstance(tab_ref, dict):
            name = tab_ref.get("name")
            if name in self.tabs:
                return self.tabs[name]
            raise TabNotFoundError(f"no tab named '{name}' has been opened")

        if tab_ref in (None, "", "current"):
            return self.driver.current_window_handle
        if tab_ref == "latest":
            return handles[-1]
        if tab_ref == "opener":
            try:
                current = self.driver.current_window_handle
            except NoSuchWindowException:
                current = None
            opener = self.openers.get(current) if current else None
            return opener or self.root_handle
        if tab_ref in self.tabs:
            return self.tabs[tab_ref]
        if tab_ref in handles:  # already a raw handle
            return tab_ref
        raise TabNotFoundError(f"no tab named '{tab_ref}' has been opened")


# --------------------------------------------------------------------------
# action implementations
# --------------------------------------------------------------------------
_KEY_ALIASES = {
    "enter": Keys.ENTER,
    "return": Keys.ENTER,
    "tab": Keys.TAB,
    "escape": Keys.ESCAPE,
    "esc": Keys.ESCAPE,
    "space": Keys.SPACE,
    "backspace": Keys.BACKSPACE,
    "delete": Keys.DELETE,
    "arrowup": Keys.ARROW_UP,
    "arrowdown": Keys.ARROW_DOWN,
    "arrowleft": Keys.ARROW_LEFT,
    "arrowright": Keys.ARROW_RIGHT,
    "home": Keys.HOME,
    "end": Keys.END,
    "pageup": Keys.PAGE_UP,
    "pagedown": Keys.PAGE_DOWN,
}

_MODIFIER_KEYS = {
    "shift": Keys.SHIFT,
    "ctrl": Keys.CONTROL,
    "control": Keys.CONTROL,
    "alt": Keys.ALT,
    "meta": Keys.META,
    "command": Keys.META,
}


def _find(driver, step: Step, ctx: ExecutionContext, *, require_visible: bool = True):
    return resolve_element(
        driver,
        step.target,
        timeout_ms=config.DEFAULT_TIMEOUT_MS,
        require_visible=require_visible,
        frame_context=ctx.frame_stack,
    )


def _click_element(driver, element, button: str = "left", click_count: int = 1) -> None:
    if button == "right":
        ActionChains(driver).context_click(element).perform()
        return
    if button == "middle":
        driver.execute_script(
            "arguments[0].dispatchEvent(new MouseEvent('auxclick', {button: 1, bubbles: true}));",
            element,
        )
        return
    if click_count >= 2:
        ActionChains(driver).double_click(element).perform()
        return
    try:
        element.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", element)


def _open_tab(driver, step: Step, ctx: ExecutionContext) -> Optional[dict]:
    """Bind the tab this step opened (or that a previous step caused) to a name.

    Three shapes appear in real recordings: an explicit url, a target to click
    (`options.trigger == "click_target"`), or neither — the recorder simply
    noting that a tab appeared.
    """
    opener = None
    try:
        opener = driver.current_window_handle
    except NoSuchWindowException:
        opener = ctx.root_handle

    known = ctx.bound_handles()
    url = step.options.get("url")

    if url:
        driver.switch_to.new_window("tab")
        driver.get(url)
        new_handle = driver.current_window_handle
        driver.switch_to.window(opener)
    else:
        if step.target is not None and step.options.get("trigger", "click_target") == "click_target":
            _click_element(driver, _find(driver, step, ctx))
        limit = (step.wait_after.timeout_ms if step.wait_after else config.DEFAULT_TIMEOUT_MS)
        deadline = time.monotonic() + limit / 1000
        new_handle = None
        while True:
            fresh = [h for h in driver.window_handles if h not in known]
            if fresh:
                new_handle = fresh[-1]
                break
            if time.monotonic() >= deadline:
                raise TabNotFoundError(
                    f"step '{step.id}': no new tab appeared within {limit}ms"
                )
            time.sleep(config.POLL_INTERVAL_SECONDS)

    ctx.register_tab(step.extract_as, new_handle, opener)
    # Per section 7 the active tab does not change until switch_tab.
    try:
        if driver.current_window_handle != opener:
            driver.switch_to.window(opener)
    except NoSuchWindowException:
        driver.switch_to.window(new_handle)

    return {step.extract_as: new_handle} if step.extract_as else None


def _close_tab(driver, step: Step, ctx: ExecutionContext) -> None:
    handle = ctx.resolve_tab_ref(step.options.get("tab_ref"))
    if handle not in driver.window_handles:
        # Popups routinely close themselves; nothing left to do.
        if driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])
        return
    if len(driver.window_handles) <= 1:
        raise TabNotFoundError(f"step '{step.id}': refusing to close the only open tab")

    try:
        was_active = driver.current_window_handle == handle
    except NoSuchWindowException:
        was_active = True

    driver.switch_to.window(handle)
    driver.close()

    fallback = ctx.openers.get(handle) or ctx.root_handle
    remaining = driver.window_handles
    if fallback not in remaining:
        fallback = remaining[0]
    if was_active or True:
        driver.switch_to.window(fallback)


def _extract(driver, step: Step, ctx: ExecutionContext) -> dict:
    kind = step.options.get("extract_type", "text")
    if kind == "count":
        try:
            element = _find(driver, step, ctx, require_visible=False)
            found = 1 if element else 0
        except TargetResolutionError:
            found = 0
        return {step.extract_as: found}

    element = _find(driver, step, ctx, require_visible=(kind != "value"))
    if kind == "value":
        value = element.get_attribute("value")
    elif kind == "attribute":
        name = step.options.get("attribute_name")
        if not name:
            raise ValueError(f"step '{step.id}': extract_type 'attribute' needs options.attribute_name")
        value = element.get_attribute(name)
    elif kind == "html":
        value = element.get_attribute("innerHTML")
    else:
        value = element.text
    return {step.extract_as: value}


def _assert(driver, step: Step, ctx: ExecutionContext) -> None:
    kind = step.options.get("assert_type")
    expected = step.options.get("expected")

    if kind in ("hidden", "not_exists"):
        try:
            _find(driver, step, ctx)
        except TargetResolutionError:
            return
        raise AssertionFailedError(f"step '{step.id}': element is visible but should be {kind}")

    element = _find(driver, step, ctx, require_visible=(kind == "visible"))

    if kind == "visible":
        if not element.is_displayed():
            raise AssertionFailedError(f"step '{step.id}': element is not visible")
    elif kind == "enabled":
        if not element.is_enabled():
            raise AssertionFailedError(f"step '{step.id}': element is not enabled")
    elif kind == "disabled":
        if element.is_enabled():
            raise AssertionFailedError(f"step '{step.id}': element is not disabled")
    elif kind == "text_equals":
        if element.text != expected:
            raise AssertionFailedError(
                f"step '{step.id}': text is {element.text!r}, expected {expected!r}"
            )
    elif kind == "text_contains":
        if str(expected) not in element.text:
            raise AssertionFailedError(
                f"step '{step.id}': text {element.text!r} does not contain {expected!r}"
            )
    elif kind == "value_equals":
        actual = element.get_attribute("value")
        if actual != expected:
            raise AssertionFailedError(
                f"step '{step.id}': value is {actual!r}, expected {expected!r}"
            )
    elif kind == "count_equals":
        by, value = _locator_for(step.target.selectors[0])
        actual = len(driver.find_elements(by, value))
        if actual != int(expected):
            raise AssertionFailedError(
                f"step '{step.id}': found {actual} elements, expected {expected}"
            )
    else:
        raise ValueError(f"step '{step.id}': unsupported assert_type {kind!r}")


def _alert(driver, step: Step, bound_vars: dict, extracted: dict) -> Optional[dict]:
    how = step.alert_action or step.options.get("alert_action") or "accept"
    alert_input = None
    if step.value is not None:
        alert_input = _stringify(resolve_value(step.value, bound_vars, extracted))

    limit = step.wait_after.timeout_ms if step.wait_after else config.DEFAULT_TIMEOUT_MS
    deadline = time.monotonic() + limit / 1000
    while True:
        text = handle_alert(driver, how, alert_input)
        if text is not None:
            return {step.extract_as: text} if step.extract_as else None
        if time.monotonic() >= deadline:
            raise NoAlertPresentException(
                f"step '{step.id}': expected a dialog within {limit}ms but none appeared"
            )
        time.sleep(config.POLL_INTERVAL_SECONDS)


def _scroll(driver, step: Step, ctx: ExecutionContext) -> None:
    direction = step.options.get("direction", "down")
    amount = int(step.options.get("amount_px", 500))
    if direction == "to_element":
        element = _find(driver, step, ctx, require_visible=False)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        return
    delta = -amount if direction == "up" else amount
    driver.execute_script("window.scrollBy(0, arguments[0]);", delta)


def _key_press(driver, step: Step, ctx: ExecutionContext) -> None:
    key_name = str(step.options.get("key", ""))
    key = _KEY_ALIASES.get(key_name.lower(), key_name)
    modifiers = [_MODIFIER_KEYS[m.lower()] for m in step.options.get("modifiers", []) if m.lower() in _MODIFIER_KEYS]

    element = _find(driver, step, ctx) if step.target else None
    chain = ActionChains(driver)
    if element is not None:
        chain = chain.move_to_element(element).click(element)
    for mod in modifiers:
        chain = chain.key_down(mod)
    chain = chain.send_keys(key)
    for mod in reversed(modifiers):
        chain = chain.key_up(mod)
    chain.perform()


def _set_checkbox(driver, step: Step, ctx: ExecutionContext, want_checked: bool) -> None:
    element = _find(driver, step, ctx)
    if element.is_selected() != want_checked:
        _click_element(driver, element)


def dispatch(
    driver,
    step: Step,
    bound_vars: dict,
    extracted: dict,
    ctx: ExecutionContext,
) -> Optional[dict[str, Any]]:
    action = step.action

    # --- navigation / tabs -------------------------------------------------
    if action == ActionType.NAVIGATE.value:
        driver.get(str(step.options.get("url")))
    elif action == ActionType.BACK.value:
        driver.back()
    elif action == ActionType.FORWARD.value:
        driver.forward()
    elif action == ActionType.RELOAD.value:
        driver.refresh()
    elif action == ActionType.OPEN_TAB.value:
        return _open_tab(driver, step, ctx)
    elif action == ActionType.SWITCH_TAB.value:
        driver.switch_to.window(ctx.resolve_tab_ref(step.options.get("tab_ref", "latest")))
        ctx.frame_stack = []
    elif action == ActionType.CLOSE_TAB.value:
        _close_tab(driver, step, ctx)
        ctx.frame_stack = []
    elif action == ActionType.RESIZE_WINDOW.value:
        driver.set_window_size(int(step.options["width"]), int(step.options["height"]))

    # --- mouse / keyboard / forms -----------------------------------------
    elif action == ActionType.CLICK.value:
        _click_element(
            driver,
            _find(driver, step, ctx),
            step.options.get("button", "left"),
            int(step.options.get("click_count", 1)),
        )
    elif action == ActionType.DBLCLICK.value:
        ActionChains(driver).double_click(_find(driver, step, ctx)).perform()
    elif action == ActionType.RIGHT_CLICK.value:
        ActionChains(driver).context_click(_find(driver, step, ctx)).perform()
    elif action == ActionType.HOVER.value:
        ActionChains(driver).move_to_element(_find(driver, step, ctx)).perform()
    elif action == ActionType.DRAG_AND_DROP.value:
        source = _find(driver, step, ctx)
        drop_spec = step.options.get("target_selector")
        if not drop_spec:
            raise ValueError(f"step '{step.id}': drag_and_drop needs options.target_selector")
        drop_target = resolve_element(
            driver,
            Target(selectors=[Selector(**drop_spec)]),
            frame_context=ctx.frame_stack,
        )
        ActionChains(driver).drag_and_drop(source, drop_target).perform()
    elif action == ActionType.INPUT.value:
        element = _find(driver, step, ctx)
        if step.options.get("clear_first", True):
            element.clear()
        element.send_keys(_stringify(resolve_value(step.value, bound_vars, extracted)))
    elif action == ActionType.CLEAR.value:
        _find(driver, step, ctx).clear()
    elif action == ActionType.KEY_PRESS.value:
        _key_press(driver, step, ctx)
    elif action == ActionType.SELECT_OPTION.value:
        select = Select(_find(driver, step, ctx))
        wanted = _stringify(resolve_value(step.value, bound_vars, extracted))
        by = step.options.get("by", "value")
        if by == "label":
            select.select_by_visible_text(wanted)
        elif by == "index":
            select.select_by_index(int(wanted))
        else:
            try:
                select.select_by_value(wanted)
            except Exception:
                select.select_by_visible_text(wanted)
    elif action == ActionType.CHECK.value:
        _set_checkbox(driver, step, ctx, True)
    elif action == ActionType.UNCHECK.value:
        _set_checkbox(driver, step, ctx, False)
    elif action == ActionType.RADIO_SELECT.value:
        element = _find(driver, step, ctx)
        if not element.is_selected():
            _click_element(driver, element)
    elif action == ActionType.UPLOAD_FILE.value:
        element = _find(driver, step, ctx, require_visible=False)
        paths = resolve_value(step.value, bound_vars, extracted)
        if isinstance(paths, (list, tuple)):
            element.send_keys("\n".join(str(p) for p in paths))
        else:
            element.send_keys(str(paths))

    # --- dialogs / context -------------------------------------------------
    elif action == ActionType.ALERT.value:
        return _alert(driver, step, bound_vars, extracted)
    elif action == ActionType.IFRAME_ENTER.value:
        ctx.frame_stack = list(ctx.frame_stack) + [step.target.selectors[0]]
        enter_frames(driver, ctx.frame_stack)
    elif action == ActionType.IFRAME_EXIT.value:
        ctx.frame_stack = ctx.frame_stack[:-1]
        enter_frames(driver, ctx.frame_stack)
    elif action == ActionType.SCROLL.value:
        _scroll(driver, step, ctx)
    elif action == ActionType.FOCUS.value:
        driver.execute_script("arguments[0].focus();", _find(driver, step, ctx))
    elif action == ActionType.BLUR.value:
        driver.execute_script("arguments[0].blur();", _find(driver, step, ctx, require_visible=False))

    # --- extraction / verification ----------------------------------------
    elif action == ActionType.EXTRACT.value:
        return _extract(driver, step, ctx)
    elif action == ActionType.ASSERT.value:
        _assert(driver, step, ctx)
    elif action == ActionType.SCREENSHOT.value:
        path = capture_screenshot(driver, config.SCREENSHOTS_DIR, "screenshot", step.id)
        return {step.extract_as: path} if step.extract_as else None
    elif action == ActionType.WAIT.value:
        perform_wait(driver, _wait_from_options(step), ctx)

    else:
        raise UnsupportedActionError(f"step '{step.id}': unknown action '{action}'")

    return None


def _wait_from_options(step: Step):
    """Build a Wait for the standalone `wait` action (section 10)."""
    from schema import Wait  # local import keeps the module import graph flat

    if step.options:
        try:
            return Wait(**{k: v for k, v in step.options.items() if k in Wait.model_fields})
        except Exception:
            pass
    return step.wait_after or Wait()


def execute_step(
    driver,
    step: Step,
    bound_vars: dict,
    extracted: dict,
    ctx: ExecutionContext,
    alerts_seen: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    def note(text: Optional[str]) -> None:
        if text is not None and alerts_seen is not None:
            alerts_seen.append(text)

    # An "alert" step wants to find the dialog itself; every other step has to
    # get it out of the way first, since it blocks all other browser commands.
    if step.action != ActionType.ALERT.value:
        note(auto_handle_alert(driver))

    perform_wait(driver, step.wait_before, ctx)

    try:
        produced = dispatch(driver, step, bound_vars, extracted, ctx)
    except UnexpectedAlertPresentException:
        # A dialog opened partway through the step (a login notice, say).
        # Close it and give the step one more go.
        note(auto_handle_alert(driver))
        produced = dispatch(driver, step, bound_vars, extracted, ctx)

    perform_wait(driver, step.wait_after, ctx)
    return produced


def capture_screenshot(driver, screenshot_dir: str, recording_id: str, step_id: str) -> Optional[str]:
    try:
        os.makedirs(screenshot_dir, exist_ok=True)
        path = os.path.join(screenshot_dir, f"{recording_id}_{step_id}_{int(time.time())}.png")
        driver.save_screenshot(path)
        return path
    except Exception:
        return None
