import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

# How long to keep looking for an element before giving up.
DEFAULT_TIMEOUT_MS = int(os.environ.get("MCP_TOOL_GENERATOR_DEFAULT_TIMEOUT_MS", "10000"))
POLL_INTERVAL_SECONDS = 0.25

# A wait with no wait_until means "fixed_delay" in the recording spec. Replays
# would spend most of their time asleep if every step's timeout were slept
# through, so by default the timeout is treated as an upper bound and the step
# continues as soon as the page is loaded.
#   "settle" (default) - wait until loaded, at most timeout_ms
#   "sleep"            - sleep the full timeout_ms, exactly as written
FIXED_DELAY_MODE = os.environ.get("MCP_TOOL_GENERATOR_FIXED_DELAY_MODE", "settle").strip().lower()
SETTLE_DELAY_MS = int(os.environ.get("MCP_TOOL_GENERATOR_SETTLE_DELAY_MS", "300"))

# The last step often kicks off a navigation (a login submit, a form post), so
# the final screenshot has to wait for the browser to land on the next page —
# otherwise it captures the page being left behind. First wait for the document
# to finish loading, then pause briefly for rendering / late XHR content.
PAGE_SETTLE_TIMEOUT_MS = int(os.environ.get("MCP_TOOL_GENERATOR_PAGE_SETTLE_TIMEOUT_MS", "10000"))
FINAL_SCREENSHOT_DELAY_MS = int(os.environ.get("MCP_TOOL_GENERATOR_FINAL_SCREENSHOT_DELAY_MS", "1500"))

HEADLESS = os.environ.get("MCP_TOOL_GENERATOR_HEADLESS", "0") == "1"

# How the browser window is shown while a recording replays:
#   "visible"    - normal window (default)
#   "background" - real window parked off-screen; it never steals focus, and
#                  screenshots still render correctly
#   "headless"   - no window at all. Fastest, but some corporate login pages
#                  (SSO in particular) behave differently or refuse headless.
# MCP_TOOL_GENERATOR_HEADLESS=1 still works and means "headless".
WINDOW_MODE = (
    os.environ.get("MCP_TOOL_GENERATOR_WINDOW_MODE", "").strip().lower()
    or ("headless" if HEADLESS else "visible")
)

# Leave the browser window open after a tool call finishes, so the end state
# stays on screen and can be worked with by hand. Windows accumulate one per
# tool call, so set this to 0 for automated/repeated runs.
KEEP_BROWSER_OPEN = os.environ.get("MCP_TOOL_GENERATOR_KEEP_BROWSER", "1") == "1"

# What to do when a javascript alert/confirm/prompt dialog appears:
#   "accept"  - press OK (default; this is what a login notice usually needs)
#   "dismiss" - press Cancel
#   "error"   - leave it and fail the step, so the recording author can decide
# A dialog blocks every other browser command until it is closed, so this is
# what keeps a replay from dying the moment an unexpected notice pops up.
ALERT_ACTION = os.environ.get("MCP_TOOL_GENERATOR_ALERT_ACTION", "accept").strip().lower()

# Login is deliberately left out of recordings — capturing credentials would be
# a security problem — but most systems need it first. These steps run ahead of
# every recording: open start_url, wait for the person to sign in by hand, then
# get the window out of the way before the recorded steps run.
#
# Off by default so local runs don't sit waiting for a human. Point it at a
# prelude file to turn it on.
# A relative path is taken from the project folder, not from wherever the
# server happened to be started — an MCP client launches it with a working
# directory of its own choosing, and a prelude that silently fails to load
# would mean no waiting for sign-in at all.
_prelude = os.environ.get("MCP_TOOL_GENERATOR_LOGIN_PRELUDE") or None
LOGIN_PRELUDE_FILE = (
    None if not _prelude else _prelude if os.path.isabs(_prelude) else os.path.join(BASE_DIR, _prelude)
)

# After signing in, the system usually lands on its own home page rather than
# the page the recording starts from, so go back to start_url before replaying.
LOGIN_PRELUDE_RENAVIGATE = os.environ.get("MCP_TOOL_GENERATOR_LOGIN_RENAVIGATE", "1") == "1"

# Reusing one browser profile keeps the session cookie, so a later tool call can
# find itself already signed in instead of asking the person again.
USER_DATA_DIR = os.environ.get("MCP_TOOL_GENERATOR_USER_DATA_DIR") or None

# Where a window sits when visible, and where it goes to get out of the way.
VISIBLE_WINDOW_POSITION = (40, 40)
OFFSCREEN_WINDOW_POSITION = (-32000, -32000)

# "edge" (default) or "chrome"
BROWSER = os.environ.get("MCP_TOOL_GENERATOR_BROWSER", "edge")

# Explicit path to a chromedriver.exe / msedgedriver.exe binary. Selenium
# normally auto-downloads the matching driver on first use, which requires
# internet access — set this when running somewhere without it (e.g. an
# internal/air-gapped network) so the driver doesn't need to be fetched.
# Leave unset to keep the automatic behavior.
DRIVER_PATH = os.environ.get("MCP_TOOL_GENERATOR_DRIVER_PATH") or None
