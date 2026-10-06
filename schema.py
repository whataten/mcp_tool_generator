"""Recording JSON schema — see docs/recordings_rule.md.

Two deliberate choices about strictness, both from section 13 of that document:

* `Step.action` is a plain string, not an enum. A recording that uses an action
  this executor has not learned yet still loads and registers; only the unknown
  step fails, under its own `on_error` policy. Rejecting the whole file would
  take the entire tool offline over one step.
* Unknown fields are ignored rather than rejected, so recorder versions can add
  fields ahead of the executor.
"""
import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

_ID_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


# --------------------------------------------------------------------------
# variables (section 3)
# --------------------------------------------------------------------------
class VarType(str, Enum):
    STRING = "string"
    SECRET = "secret"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    FILE_PATH = "file_path"


class VariableSpec(BaseModel):
    type: VarType
    required: bool = True
    description: str = ""
    default: Optional[Any] = None
    options: Optional[list[str]] = None
    sensitive: Optional[bool] = None

    @model_validator(mode="after")
    def _check_shape(self):
        if self.type == VarType.ENUM and not self.options:
            raise ValueError("a variable of type 'enum' needs an options list")
        return self

    @property
    def is_sensitive(self) -> bool:
        if self.type == VarType.SECRET:
            return True
        return bool(self.sensitive)


# --------------------------------------------------------------------------
# target (section 4)
# --------------------------------------------------------------------------
class SelectorType(str, Enum):
    CSS = "css"
    XPATH = "xpath"
    TEXT = "text"
    ROLE = "role"
    TEST_ID = "test_id"
    ARIA_LABEL = "aria_label"
    PLACEHOLDER = "placeholder"


class Selector(BaseModel):
    type: SelectorType
    value: str
    exact: bool = True
    role_name: Optional[str] = None


class Target(BaseModel):
    selectors: list[Selector] = Field(min_length=1)
    nth: int = 0
    frame_path: list[Selector] = []
    scroll_into_view: bool = True


# --------------------------------------------------------------------------
# value (section 5)
# --------------------------------------------------------------------------
class ValueSource(BaseModel):
    type: Literal["literal", "variable", "extracted_ref", "expression"]
    name: Optional[str] = None
    value: Optional[Any] = None

    @model_validator(mode="after")
    def _check_shape(self):
        if self.type in ("variable", "extracted_ref") and not self.name:
            raise ValueError(f"value.name is required when value.type == '{self.type}'")
        if self.type in ("literal", "expression") and self.value is None:
            raise ValueError(f"value.value is required when value.type == '{self.type}'")
        return self


# --------------------------------------------------------------------------
# step common fields (section 6)
# --------------------------------------------------------------------------
class WaitUntil(str, Enum):
    FIXED_DELAY = "fixed_delay"
    SELECTOR_VISIBLE = "selector_visible"
    SELECTOR_HIDDEN = "selector_hidden"
    NETWORK_IDLE = "network_idle"
    DOM_CONTENT_LOADED = "dom_content_loaded"
    LOAD = "load"
    DIALOG_PRESENT = "dialog_present"


class Wait(BaseModel):
    timeout_ms: int = Field(default=5000, gt=0)
    wait_until: WaitUntil = WaitUntil.FIXED_DELAY
    target: Optional[Target] = None


class ErrorPolicy(BaseModel):
    strategy: Literal["abort", "skip", "retry"] = "abort"
    retry_count: int = 0
    retry_interval_ms: int = 1000


class Condition(BaseModel):
    source: Literal["extracted_ref", "variable"] = "extracted_ref"
    name: str
    op: Literal["equals", "contains", "exists", "not_exists"]
    value: Optional[Any] = None


# --------------------------------------------------------------------------
# actions (sections 7-10)
# --------------------------------------------------------------------------
class ActionType(str, Enum):
    # navigation / tabs
    NAVIGATE = "navigate"
    BACK = "back"
    FORWARD = "forward"
    RELOAD = "reload"
    OPEN_TAB = "open_tab"
    SWITCH_TAB = "switch_tab"
    CLOSE_TAB = "close_tab"
    RESIZE_WINDOW = "resize_window"
    # mouse / keyboard / forms
    CLICK = "click"
    DBLCLICK = "dblclick"
    RIGHT_CLICK = "right_click"
    HOVER = "hover"
    DRAG_AND_DROP = "drag_and_drop"
    INPUT = "input"
    CLEAR = "clear"
    KEY_PRESS = "key_press"
    SELECT_OPTION = "select_option"
    CHECK = "check"
    UNCHECK = "uncheck"
    RADIO_SELECT = "radio_select"
    UPLOAD_FILE = "upload_file"
    # dialogs / context
    ALERT = "alert"
    IFRAME_ENTER = "iframe_enter"
    IFRAME_EXIT = "iframe_exit"
    SCROLL = "scroll"
    FOCUS = "focus"
    BLUR = "blur"
    # extraction / verification
    EXTRACT = "extract"
    ASSERT = "assert"
    SCREENSHOT = "screenshot"
    WAIT = "wait"


# Events the recorder writes down so a trace can be read back, not instructions
# to replay. Replaying the click that caused the popup opens it again by itself,
# so acting on these would double up.
ANNOTATION_ACTIONS = frozenset({"window_open_call", "sso_popup_recover"})

_NEEDS_TARGET = frozenset(
    {
        ActionType.CLICK.value,
        ActionType.DBLCLICK.value,
        ActionType.RIGHT_CLICK.value,
        ActionType.HOVER.value,
        ActionType.DRAG_AND_DROP.value,
        ActionType.INPUT.value,
        ActionType.CLEAR.value,
        ActionType.SELECT_OPTION.value,
        ActionType.CHECK.value,
        ActionType.UNCHECK.value,
        ActionType.RADIO_SELECT.value,
        ActionType.UPLOAD_FILE.value,
        ActionType.IFRAME_ENTER.value,
        ActionType.FOCUS.value,
        ActionType.BLUR.value,
        ActionType.EXTRACT.value,
        ActionType.ASSERT.value,
    }
)

_NEEDS_VALUE = frozenset(
    {
        ActionType.INPUT.value,
        ActionType.SELECT_OPTION.value,
        ActionType.UPLOAD_FILE.value,
    }
)


class Step(BaseModel):
    id: str
    action: str
    target: Optional[Target] = None
    value: Optional[ValueSource] = None
    options: dict[str, Any] = {}
    extract_as: Optional[str] = None
    alert_action: Optional[Literal["accept", "dismiss"]] = None
    wait_before: Optional[Wait] = None
    wait_after: Optional[Wait] = None
    on_error: Optional[ErrorPolicy] = None
    condition: Optional[Condition] = None

    @property
    def is_annotation(self) -> bool:
        return self.action in ANNOTATION_ACTIONS

    @property
    def is_known(self) -> bool:
        return self.action in _KNOWN_ACTIONS or self.is_annotation

    @model_validator(mode="after")
    def _validate_shape(self):
        # Only known actions are shape-checked. An unknown one is left alone so
        # it can fail at its own step under its own on_error policy.
        if self.action not in _KNOWN_ACTIONS:
            return self

        if self.action in _NEEDS_TARGET and not self.target:
            raise ValueError(f"step '{self.id}': action '{self.action}' requires a target")

        if self.action in _NEEDS_VALUE and not self.value:
            raise ValueError(f"step '{self.id}': action '{self.action}' requires a value")

        if self.action == ActionType.NAVIGATE.value and not self.options.get("url"):
            raise ValueError(f"step '{self.id}': navigate requires options.url")

        if self.action == ActionType.EXTRACT.value and not self.extract_as:
            raise ValueError(f"step '{self.id}': extract requires extract_as")

        if self.action == ActionType.ASSERT.value and not self.options.get("assert_type"):
            raise ValueError(f"step '{self.id}': assert requires options.assert_type")

        if self.action == ActionType.KEY_PRESS.value and not self.options.get("key"):
            raise ValueError(f"step '{self.id}': key_press requires options.key")

        if self.action == ActionType.RESIZE_WINDOW.value:
            if not self.options.get("width") or not self.options.get("height"):
                raise ValueError(
                    f"step '{self.id}': resize_window requires options.width and options.height"
                )

        return self


_KNOWN_ACTIONS = frozenset(a.value for a in ActionType)


# --------------------------------------------------------------------------
# root (section 2)
# --------------------------------------------------------------------------
class Recording(BaseModel):
    schema_version: int = 1
    id: str
    name: str
    description: str = Field(min_length=10)
    start_url: str
    variables: dict[str, VariableSpec] = {}
    steps: list[Step] = Field(min_length=1)
    outputs: Optional[list[str]] = None
    metadata: dict[str, Any] = {}

    @field_validator("id")
    @classmethod
    def _id_is_tool_name_safe(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError(
                f"id '{v}' is not a valid MCP tool name "
                "(must start with a letter/underscore and contain only letters, digits, underscores)"
            )
        return v

    @model_validator(mode="after")
    def _validate_references(self):
        produced: set[str] = set()
        for step in self.steps:
            if step.value and step.value.type == "variable":
                if step.value.name not in self.variables:
                    raise ValueError(
                        f"step '{step.id}' references undefined variable '{step.value.name}'"
                    )
            if step.value and step.value.type == "extracted_ref":
                if step.value.name not in produced:
                    raise ValueError(
                        f"step '{step.id}' uses extracted value '{step.value.name}', "
                        "which no earlier step produces"
                    )
            if step.extract_as:
                produced.add(step.extract_as)

        if self.outputs:
            unknown = [name for name in self.outputs if name not in produced]
            if unknown:
                raise ValueError(
                    f"outputs names {unknown} are never produced by an extract_as in this recording"
                )
        return self
