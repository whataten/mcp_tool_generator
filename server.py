import asyncio
import sys

if sys.platform == "win32":
    sys.stderr.reconfigure(encoding="utf-8")

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

import config
from mcp_registration import ToolRegistry
from recording_loader import load_all_recordings


async def main() -> None:
    recordings, load_errors = load_all_recordings(config.RECORDINGS_DIR)
    for err in load_errors:
        print(f"[WARN] {err}", file=sys.stderr)

    if not recordings:
        print(f"[WARN] no valid recordings found in {config.RECORDINGS_DIR}", file=sys.stderr)
    else:
        print(f"[INFO] registered {len(recordings)} tool(s): {', '.join(recordings)}", file=sys.stderr)

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
