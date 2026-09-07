import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

_ID_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class VarType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SECRET = "secret"


class VariableSpec(BaseModel):
    type: VarType
    required: bool = True
    description: str = ""
    default: Optional[Any] = None


class SelectorType(str, Enum):
    CSS = "css"
    XPATH = "xpath"


class Selector(BaseModel):
    type: SelectorType
    value: str


class Target(BaseModel):
    selectors: list[Selector] = Field(min_length=1)


class ValueSource(BaseModel):
    # "variable"  - a tool argument
    # "literal"   - a fixed value written into the recording
    # "extracted" - a value an earlier extract step read off the page, which is
    #               how a string copied from one place gets pasted into another
    type: Literal["variable", "literal", "extracted"]
    name: Optional[str] = None
    value: Optional[Any] = None

    @model_validator(mode="after")
    def _check_shape(self):
        if self.type == "variable" and not self.name:
            raise ValueError("value.name is required when value.type == 'variable'")
        if self.type == "extracted" and not self.name:
            raise ValueError("value.name is required when value.type == 'extracted'")
        if self.type == "literal" and self.value is None:
            raise ValueError("value.value is required when value.type == 'literal'")
        return self


class WaitAfter(BaseModel):
    timeout_ms: int = Field(default=5000, gt=0)


class ActionType(str, Enum):
    INPUT = "input"
    CLICK = "click"
    SELECT = "select"
    WAIT = "wait"
    NAVIGATE = "navigate"
    EXTRACT = "extract"
    ALERT = "alert"
    SWITCH_WINDOW = "switch_window"
    CLOSE_WINDOW = "close_window"


class Step(BaseModel):
    id: str
    action: ActionType
    target: Optional[Target] = None
    value: Optional[ValueSource] = None
    extract_as: Optional[str] = None
    extract_attribute: Optional[str] = None
    # For action "alert": how to close the dialog, and text to type into a
    # prompt() dialog. Set extract_as to also capture the dialog's message.
    alert_action: Optional[Literal["accept", "dismiss"]] = None
    alert_input: Optional[str] = None
    # For action "switch_window": which window to move to.
    #   "new"      - the most recently opened one (waits for it to appear)
    #   "original" - the window the recording started in
    #   "match"    - the one whose URL or title contains window_match
    window_target: Optional[Literal["new", "original", "match"]] = None
    window_match: Optional[str] = None
    wait_after: Optional[WaitAfter] = None

    @model_validator(mode="after")
    def _validate_shape(self):
        needs_target = self.action in (
            ActionType.INPUT,
            ActionType.CLICK,
            ActionType.SELECT,
            ActionType.EXTRACT,
        )
        if needs_target and not self.target:
            raise ValueError(f"step '{self.id}': action '{self.action}' requires a target")

        if self.action in (ActionType.INPUT, ActionType.SELECT) and not self.value:
            raise ValueError(f"step '{self.id}': action '{self.action}' requires a value")

        if self.action == ActionType.NAVIGATE and not self.value:
            raise ValueError(f"step '{self.id}': navigate requires a value (destination URL)")

        if self.action == ActionType.EXTRACT and not self.extract_as:
            raise ValueError(f"step '{self.id}': extract requires extract_as")

        if self.action == ActionType.SWITCH_WINDOW:
            if not self.window_target:
                raise ValueError(f"step '{self.id}': switch_window requires window_target")
            if self.window_target == "match" and not self.window_match:
                raise ValueError(
                    f"step '{self.id}': switch_window with window_target 'match' requires window_match"
                )

        return self


class Recording(BaseModel):
    schema_version: Literal[1] = 1
    id: str
    name: str
    description: str = Field(min_length=10)
    start_url: str
    variables: dict[str, VariableSpec] = {}
    steps: list[Step] = Field(min_length=1)

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
    def _validate_value_references(self):
        produced: set[str] = set()
        for step in self.steps:
            if step.value and step.value.type == "variable":
                if step.value.name not in self.variables:
                    raise ValueError(
                        f"step '{step.id}' references undefined variable '{step.value.name}'"
                    )
            if step.value and step.value.type == "extracted":
                if step.value.name not in produced:
                    raise ValueError(
                        f"step '{step.id}' uses extracted value '{step.value.name}', "
                        "which no earlier step produces"
                    )
            if step.extract_as:
                produced.add(step.extract_as)
        return self
