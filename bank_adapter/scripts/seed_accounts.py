"""仮名 user_id → 口座ラベルの対応表を、`bank` データベースに入れる（コミット禁止のファイルから）。

使い方: uv run python scripts/seed_accounts.py accounts.local.json
ファイルの形: {"user_001": "acct01", "user_002": "acct02", ...}（口座番号・トークンは入れない）
"""

import json
import sys

from src.config import get_settings
from src.db.store import FirestoreStore

if __name__ == "__main__":
    s = get_settings()
    store = FirestoreStore(project=s.google_cloud_project, database=s.firestore_database)
    mapping = json.load(open(sys.argv[1]))
    for user_id, label in mapping.items():
        store.set_label(user_id, label)
    print(f"{len(mapping)} 件を登録した")
