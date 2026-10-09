"""Agent Registry に貼る、`/mcp` のツールの一覧（`mcp_toolspec.json`）を書き出す（TASKS B21）。

非公開の MCP サーバーは、Registry の「URL からツールを取り込む」が使えないので、この一覧を
貼る（ユーザーの Console 作業。docs/guides/agent_platform_human_steps.md 4章）。
ツールを足したら再生成する。
使い方（`backend/` で）: uv run python scripts/export_toolspec.py
"""

import asyncio
import json
from pathlib import Path

from src.routers.mcp import mcp

OUT = Path(__file__).resolve().parents[1] / "mcp_toolspec.json"


async def build() -> dict:
    tools = await mcp.list_tools()
    return {
        "tools": [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in sorted(tools, key=lambda t: t.name)
        ]
    }


if __name__ == "__main__":
    spec = asyncio.run(build())
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(spec['tools'])} 件のツールを {OUT.name} に書き出しました。")
