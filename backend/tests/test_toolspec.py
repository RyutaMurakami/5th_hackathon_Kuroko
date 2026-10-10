"""Registry に貼る toolspec が、実際の `/mcp` のツールと一致している（足したら再生成する）。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from export_toolspec import OUT, build  # noqa: E402


async def test_committed_toolspec_matches_the_live_tools():
    assert json.loads(OUT.read_text(encoding="utf-8")) == await build(), (
        "mcp_toolspec.json が古い。`uv run python scripts/export_toolspec.py` で再生成する"
    )
