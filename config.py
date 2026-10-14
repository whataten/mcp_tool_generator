"""Settings, all from environment variables.

Every value is validated here rather than where it is used. A typo in a
setting used to change behaviour silently — `ALERT_ACTION=dismis` pressed OK on
dialogs it was meant to cancel — and a non-numeric timeout stopped the server
from starting at all with a bare traceback. Bad values now fall back to the
default and are collected in CONFIG_WARNINGS, which server.py prints on startup
alongside the settings actually in effect.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

# Filled in by the readers below; printed by server.py at startup.
CONFIG_WARNINGS: list[str] = []


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        CONFIG_WARNINGS.append(f"{name}={raw!r} is not a whole number; using {default}")
        return default
    if value < minimum:
        CONFIG_WARNINGS.append(f"{name}={value} is below {minimum}; using {default}")
        return default
    return value


def _choice_env(name: str, default: str, allowed: tuple[str, ...]) -> str:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw not in allowed:
        CONFIG_WARNINGS.append(
            f"{name}={raw!r} is not one of {', '.join(allowed)}; using {default!r}"
        )
        return default
    return raw


def _bool_env(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    CONFIG_WARNINGS.append(f"{name}={raw!r} is not a yes/no value; using {default}")
    return default


def _path_env(name: str) -> "str | None":
    """A path from the environment, relative ones taken from the project folder.

    An MCP client starts the server with a working directory of its own
    choosing, so a relative path resolved against the process's cwd would go
    missing.
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return None
    return raw if os.path.isabs(raw) else os.path.join(BASE_DIR, raw)


# How long to keep looking for an element before giving up.
DEFAULT_TIMEOUT_MS = _int_env("MCP_TOOL_GENERATOR_DEFAULT_TIMEOUT_MS", 10000, minimum=1)
POLL_INTERVAL_SECONDS = 0.25

# A wait with no wait_until means "fixed_delay" in the recording spec. Replays
# would spend most of their time asleep if every step's timeout were slept
# through, so by default the timeout is treated as an upper bound and the step
# continues as soon as the page is loaded.
#   "settle" (default) - wait until loaded, at most timeout_ms
#   "sleep"            - sleep the full timeout_ms, exactly as written
FIXED_DELAY_MODE = _choice_env("MCP_TOOL_GENERATOR_FIXED_DELAY_MODE", "settle", ("settle", "sleep"))
SETTLE_DELAY_MS = _int_env("MCP_TOOL_GENERATOR_SETTLE_DELAY_MS", 300)

# The last step often kicks off a navigation (a login submit, a form post), so
# the final screenshot has to wait for the browser to land on the next page —
# otherwise it captures the page being left behind. First wait for the document
# to finish loading, then pause briefly for rendering / late XHR content.
PAGE_SETTLE_TIMEOUT_MS = _int_env("MCP_TOOL_GENERATOR_PAGE_SETTLE_TIMEOUT_MS", 10000)
FINAL_SCREENSHOT_DELAY_MS = _int_env("MCP_TOOL_GENERATOR_FINAL_SCREENSHOT_DELAY_MS", 1500)

HEADLESS = _bool_env("MCP_TOOL_GENERATOR_HEADLESS", False)

# How the browser window is shown while a recording replays:
#   "visible"    - normal window (default)
#   "background" - real window parked off-screen; it never steals focus, and
#                  screenshots still render correctly
#   "headless"   - no window at all. Fastest, but some corporate login pages
#                  (SSO in particular) behave differently or refuse headless.
# MCP_TOOL_GENERATOR_HEADLESS=1 still works and means "headless".
WINDOW_MODE = _choice_env(
    "MCP_TOOL_GENERATOR_WINDOW_MODE",
    "headless" if HEADLESS else "visible",
    ("visible", "background", "headless"),
)

# Leave the browser window open after a tool call finishes, so the end state
# stays on screen and can be worked with by hand. Windows accumulate one per
# tool call, so set this to 0 for automated/repeated runs.
KEEP_BROWSER_OPEN = _bool_env("MCP_TOOL_GENERATOR_KEEP_BROWSER", True)

# What to do when a javascript alert/confirm/prompt dialog appears:
#   "accept"  - press OK (default; this is what a login notice usually needs)
#   "dismiss" - press Cancel
#   "error"   - leave it and fail the step, so the recording author can decide
# A dialog blocks every other browser command until it is closed, so this is
# what keeps a replay from dying the moment an unexpected notice pops up.
ALERT_ACTION = _choice_env(
    "MCP_TOOL_GENERATOR_ALERT_ACTION", "accept", ("accept", "dismiss", "error")
)

# Login is deliberately left out of recordings — capturing credentials would be
# a security problem — but most systems need it first. These steps run ahead of
# every recording: open start_url, wait for the person to sign in by hand, then
# get the window out of the way before the recorded steps run.
#
# Off by default so local runs don't sit waiting for a human.
LOGIN_PRELUDE_FILE = _path_env("MCP_TOOL_GENERATOR_LOGIN_PRELUDE")

# After signing in, the system usually lands on its own home page rather than
# the page the recording starts from, so go back to start_url before replaying.
LOGIN_PRELUDE_RENAVIGATE = _bool_env("MCP_TOOL_GENERATOR_LOGIN_RENAVIGATE", True)

# Reusing one browser profile keeps the session cookie, so a later tool call can
# find itself already signed in instead of asking the person again.
USER_DATA_DIR = _path_env("MCP_TOOL_GENERATOR_USER_DATA_DIR")

# Where a window sits when visible, and where it goes to get out of the way.
VISIBLE_WINDOW_POSITION = (40, 40)
OFFSCREEN_WINDOW_POSITION = (-32000, -32000)

BROWSER = _choice_env("MCP_TOOL_GENERATOR_BROWSER", "edge", ("edge", "chrome"))

# Explicit path to a chromedriver.exe / msedgedriver.exe binary. Selenium
# normally auto-downloads the matching driver on first use, which requires
# internet access — set this when running somewhere without it (e.g. an
# internal/air-gapped network) so the driver doesn't need to be fetched.
DRIVER_PATH = _path_env("MCP_TOOL_GENERATOR_DRIVER_PATH")

# Log every step to stderr as it runs. For working out where a replay goes
# wrong when the result alone is not enough.
DEBUG = _bool_env("MCP_TOOL_GENERATOR_DEBUG", False)


def effective_settings() -> dict:
    """The settings actually in use, for the startup banner."""
    return {
        "browser": BROWSER,
        "window_mode": WINDOW_MODE,
        "keep_browser_open": KEEP_BROWSER_OPEN,
        "alert_action": ALERT_ACTION,
        "driver_path": DRIVER_PATH or "(auto-download)",
        "user_data_dir": USER_DATA_DIR or "(fresh profile each run)",
        "login_prelude": LOGIN_PRELUDE_FILE or "(off — no wait for sign-in)",
        "login_renavigate": LOGIN_PRELUDE_RENAVIGATE,
        "default_timeout_ms": DEFAULT_TIMEOUT_MS,
        "fixed_delay_mode": FIXED_DELAY_MODE,
        "recordings_dir": RECORDINGS_DIR,
        "debug": DEBUG,
    }
