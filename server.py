import asyncio
import sys

if sys.platform == "win32":
    sys.stderr.reconfigure(encoding="utf-8")

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

import config
from mcp_registration import ToolRegistry
from recording_loader import load_all_recordings


def _report_startup(recordings, load_errors) -> None:
    """Say what settings are in force and what was loaded.

    Everything here goes to stderr; stdout carries the MCP protocol. When a run
    misbehaves in a place where nobody can attach a debugger, this banner is
    the first thing worth reading.
    """
    for warning in config.CONFIG_WARNINGS:
        print(f"[WARN] setting: {warning}", file=sys.stderr)

    print("[INFO] settings in effect:", file=sys.stderr)
    for key, value in config.effective_settings().items():
        print(f"[INFO]   {key} = {value}", file=sys.stderr)

    for err in load_errors:
        print(f"[WARN] {err}", file=sys.stderr)

    if not recordings:
        print(f"[WARN] no valid recordings found in {config.RECORDINGS_DIR}", file=sys.stderr)
    else:
        print(f"[INFO] registered {len(recordings)} tool(s): {', '.join(recordings)}", file=sys.stderr)


async def main() -> None:
    recordings, load_errors = load_all_recordings(config.RECORDINGS_DIR)
    _report_startup(recordings, load_errors)

    registry = ToolRegistry(recordings)

    server = Server(
        "mcp-tool-generator",
        on_list_tools=registry.list_tools,
        on_call_tool=registry.call_tool,
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
