"""server.py를 서브프로세스로 띄우고 실제 MCP 프로토콜(stdio)로 통신하는 E2E 테스트.

Node/MCP Inspector가 없는 환경에서도 프로토콜 레벨 검증이 가능하도록 만든 스크립트.
사전 준비: `python -m http.server 8000` 을 test_page/ 디렉터리에서 실행해둘 것.
"""
import asyncio
import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def main():
    env = dict(os.environ)
    env["MCP_TOOL_GENERATOR_BROWSER"] = "edge"
    env["MCP_TOOL_GENERATOR_HEADLESS"] = "1"

    params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(PROJECT_DIR, "server.py")],
        env=env,
        cwd=PROJECT_DIR,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            print("=== list_tools ===")
            for t in tools_result.tools:
                print(f"- {t.name}: {t.description}")
            assert any(t.name == "place_purchase_order" for t in tools_result.tools)

            print("\n=== call_tool (expect success) ===")
            result = await session.call_tool(
                "place_purchase_order",
                {"sku": "SKU-1001", "quantity": 2, "note": "e2e test"},
            )
            payload = json.loads(result.content[0].text)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            assert payload["status"] == "success"
            assert "Order #12345" in payload["extracted"]["confirmation_message"]

            print("\nALL MCP PROTOCOL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
