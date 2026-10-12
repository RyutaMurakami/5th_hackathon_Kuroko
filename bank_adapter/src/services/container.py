"""設定から BankService を組み立てる。

スタブと実機、メモリと Firestore は設定だけで切り替える（TASKS E5）。
"""

from functools import lru_cache

from src.clients.bank import BankClient
from src.clients.demo_bank import DemoBank
from src.clients.stub_bank import StubBank
from src.clients.sunabar import SunabarBank, secret_manager_tokens
from src.config import get_settings
from src.db.store import FirestoreStore, MemoryStore, Store
from src.services.transfers import BankService


@lru_cache
def get_service() -> BankService:
    s = get_settings()
    store: Store
    if s.store_backend == "firestore":
        store = FirestoreStore(project=s.google_cloud_project, database=s.firestore_database)
    else:
        store = MemoryStore()
    bank: BankClient
    if s.bank_mode == "sunabar":
        bank = SunabarBank(
            base_url=s.sunabar_base_url,
            load_tokens=secret_manager_tokens(s.sunabar_tokens_secret),
        )
    else:
        bank = StubBank(auto_approve=s.environment == "local")
    live = frozenset(x.strip() for x in s.demo_live_payer_labels.split(",") if x.strip())
    if not live:
        return BankService(store=store, bank=bank, approval_ttl_seconds=s.approval_ttl_seconds)
    demo = DemoBank(real=bank, store=store, live_payer_labels=live)
    return BankService(
        store=store,
        bank=demo,
        approval_ttl_seconds=s.approval_ttl_seconds,
        is_simulated=demo.is_simulated,
        demo=demo,
    )
