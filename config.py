import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

DEFAULT_TIMEOUT_MS = 5000
POLL_INTERVAL_SECONDS = 0.25

HEADLESS = os.environ.get("MCP_TOOL_GENERATOR_HEADLESS", "0") == "1"

# "edge" (default) or "chrome"
BROWSER = os.environ.get("MCP_TOOL_GENERATOR_BROWSER", "edge")

# Explicit path to a chromedriver.exe / msedgedriver.exe binary. Selenium
# normally auto-downloads the matching driver on first use, which requires
# internet access — set this when running somewhere without it (e.g. an
# internal/air-gapped network) so the driver doesn't need to be fetched.
# Leave unset to keep the automatic behavior.
DRIVER_PATH = os.environ.get("MCP_TOOL_GENERATOR_DRIVER_PATH") or None
