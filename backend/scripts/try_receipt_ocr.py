"""領収書の画像を、本物の Gemini で読み取る確認（TASKS B19。お金は動かない）。

使い方（`backend/` で）: uv run python scripts/try_receipt_ocr.py <画像のパス>
"""

import asyncio
import json
import sys
from pathlib import Path

from src.services.receipt_ocr import GeminiReceiptModel, ocr_receipt

PROJECT = "kuroko-509311"


async def main(path: str) -> None:
    result = await ocr_receipt(GeminiReceiptModel(project=PROJECT), Path(path).read_bytes())
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
