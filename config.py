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

# "edge" (default) or "chrome"
BROWSER = os.environ.get("MCP_TOOL_GENERATOR_BROWSER", "edge")

# Explicit path to a chromedriver.exe / msedgedriver.exe binary. Selenium
# normally auto-downloads the matching driver on first use, which requires
# internet access — set this when running somewhere without it (e.g. an
# internal/air-gapped network) so the driver doesn't need to be fetched.
# Leave unset to keep the automatic behavior.
DRIVER_PATH = os.environ.get("MCP_TOOL_GENERATOR_DRIVER_PATH") or None
