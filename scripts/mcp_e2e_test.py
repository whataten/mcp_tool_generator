"""server.py를 서브프로세스로 띄우고 실제 MCP 프로토콜(stdio)로 통신하는 E2E 테스트.

인자 없이 실행하면 내장된 샘플 레코딩(place_purchase_order)을 테스트합니다 (사전에
test_page/ 에서 `python -m http.server 8000` 실행 필요).

다른 레코딩(예: 사내 시스템에서 만든 레코딩)을 테스트하려면 tool id와 JSON 인자를
직접 넘기면 됩니다 — recordings/ 폴더에 해당 레코딩 JSON을 넣어둔 상태여야 합니다:

    python scripts/mcp_e2e_test.py <tool_id> '<json 인자>'
    예) python scripts/mcp_e2e_test.py search_customer_info "{\"customer_id\": \"12345\"}"

이 모드에서는 결과가 맞는지 자동으로 assert하지 않고 그대로 출력만 합니다 — 기대값을
모르는 실제 시스템 대상이라, 성공/실패와 화면(screenshot_path)을 보고 사람이 판단하는
용도입니다.

MCP_TOOL_GENERATOR_BROWSER / MCP_TOOL_GENERATOR_HEADLESS / MCP_TOOL_GENERATOR_DRIVER_PATH
환경변수를 실행 전에 미리 set 해두면 그 값을 그대로 물려받습니다 (이 스크립트가 강제로
덮어쓰지 않음 — 커스텀 모드에서는 headless 기본값도 0이라 실제 브라우저 창이 보입니다).
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

DEFAULT_TOOL = "place_purchase_order"
DEFAULT_ARGUMENTS = {"sku": "SKU-1001", "quantity": 2, "note": "e2e test"}


async def main():
    custom = len(sys.argv) >= 3
    if custom:
        tool_name = sys.argv[1]
        arguments = json.loads(sys.argv[2])
    else:
        tool_name = DEFAULT_TOOL
        arguments = DEFAULT_ARGUMENTS

    env = dict(os.environ)
    env.setdefault("MCP_TOOL_GENERATOR_BROWSER", "edge")
    env.setdefault("MCP_TOOL_GENERATOR_HEADLESS", "0" if custom else "1")

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

            if not any(t.name == tool_name for t in tools_result.tools):
                print(f"\n[ERROR] '{tool_name}' 이 등록된 tool 목록에 없습니다. recordings/ 폴더와 id를 확인하세요.")
                return

            print(f"\n=== call_tool: {tool_name} ===")
            print(f"arguments: {json.dumps(arguments, ensure_ascii=False)}")
            result = await session.call_tool(tool_name, arguments)
            payload = json.loads(result.content[0].text)
            print(json.dumps(payload, indent=2, ensure_ascii=False))

            if not custom:
                assert payload["status"] == "success"
                assert "Order #12345" in payload["extracted"]["confirmation_message"]
                print("\nALL MCP PROTOCOL CHECKS PASSED")
            else:
                print(f"\nRESULT: {payload['status']}")


if __name__ == "__main__":
    asyncio.run(main())
