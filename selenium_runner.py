import os
import time
from typing import Any, Optional

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
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


def new_driver():
    if config.BROWSER == "edge":
        options = webdriver.EdgeOptions()
        if config.HEADLESS:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
        return webdriver.Edge(options=options)

    options = webdriver.ChromeOptions()
    if config.HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    return webdriver.Chrome(options=options)


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


def resolve_value(value_source, bound_vars: dict) -> Any:
    if value_source.type == "literal":
        return value_source.value
    return bound_vars[value_source.name]


def _stringify(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def do_input(driver, step: Step, bound_vars: dict) -> None:
    el = resolve_element(driver, step.target, ActionType.INPUT, timeout_for(step))
    el.clear()
    el.send_keys(_stringify(resolve_value(step.value, bound_vars)))


def do_click(driver, step: Step, bound_vars: dict) -> None:
    el = resolve_element(driver, step.target, ActionType.CLICK, timeout_for(step))
    try:
        el.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", el)


def do_select(driver, step: Step, bound_vars: dict) -> None:
    el = resolve_element(driver, step.target, ActionType.SELECT, timeout_for(step))
    select = Select(el)
    val = _stringify(resolve_value(step.value, bound_vars))
    try:
        select.select_by_value(val)
    except Exception:
        select.select_by_visible_text(val)


def do_navigate(driver, step: Step, bound_vars: dict) -> None:
    driver.get(str(resolve_value(step.value, bound_vars)))
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


def execute_step(driver, step: Step, bound_vars: dict) -> Optional[dict[str, Any]]:
    if step.action == ActionType.INPUT:
        do_input(driver, step, bound_vars)
    elif step.action == ActionType.CLICK:
        do_click(driver, step, bound_vars)
    elif step.action == ActionType.SELECT:
        do_select(driver, step, bound_vars)
    elif step.action == ActionType.NAVIGATE:
        do_navigate(driver, step, bound_vars)
    elif step.action == ActionType.WAIT:
        do_wait(driver, step)
    elif step.action == ActionType.EXTRACT:
        return do_extract(driver, step)
    else:
        raise ValueError(f"unsupported action: {step.action}")
    return None


def capture_screenshot(driver, screenshot_dir: str, recording_id: str, step_id: str) -> Optional[str]:
    try:
        os.makedirs(screenshot_dir, exist_ok=True)
        path = os.path.join(screenshot_dir, f"{recording_id}_{step_id}_{int(time.time())}.png")
        driver.save_screenshot(path)
        return path
    except Exception:
        return None
