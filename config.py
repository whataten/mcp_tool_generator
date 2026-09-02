import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

DEFAULT_TIMEOUT_MS = 5000
POLL_INTERVAL_SECONDS = 0.25

HEADLESS = os.environ.get("MCP_TOOL_GENERATOR_HEADLESS", "0") == "1"

# "chrome" (default) or "edge" — Edge is Chromium-based and works as a drop-in
# fallback on machines without Chrome installed (e.g. this dev sandbox).
BROWSER = os.environ.get("MCP_TOOL_GENERATOR_BROWSER", "chrome")
