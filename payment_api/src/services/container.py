"""設定から各サービスを組み立てる。署名鍵・銀行・保存先は設定だけで切り替える（TASKS E5）。"""

from dataclasses import dataclass
from functools import lru_cache

from src.clients.bank_adapter import BankAdapter, HttpBankAdapter
from src.clients.fake_bank_adapter import FakeBankAdapter
from src.clients.signers import KmsSigner, LocalSigner, MandateSigner
from src.config import get_settings
from src.db.store import FirestoreStore, MemoryStore, Store
from src.services.checkout import AcceptAllCheckouts, CheckoutVerifier, RejectAllCheckouts
from src.services.mandates import MandateService
from src.services.payments import PaymentService
from src.services.policy_gate import PolicyGate


@dataclass(frozen=True)
class Services:
    mandates: MandateService
    payments: PaymentService


@lru_cache
def get_services() -> Services:
    s = get_settings()
    store: Store = (
        FirestoreStore(project=s.google_cloud_project, database=s.firestore_database)
        if s.store_backend == "firestore"
        else MemoryStore()
    )
    participant: MandateSigner
    agent: MandateSigner
    if s.signer_mode == "kms":
        participant = KmsSigner(version_name=s.kms_participant_key_version)
        agent = KmsSigner(version_name=s.kms_payment_agent_key_version)
    else:
        participant, agent = LocalSigner(), LocalSigner()
    bank: BankAdapter = (
        HttpBankAdapter(base_url=s.bank_adapter_url) if s.bank_mode == "http" else FakeBankAdapter()
    )
    # 請求側の署名の検証は B13。ローカル以外では、実装されるまで全て拒否する（fail closed）
    checkout: CheckoutVerifier = (
        AcceptAllCheckouts() if s.environment == "local" else RejectAllCheckouts()
    )
    mandates = MandateService(store=store, participant_signer=participant, agent_signer=agent)
    gate = PolicyGate(
        store=store,
        participant_signer=participant,
        bank=bank,
        checkout_verifier=checkout,
        mandate_lookup=mandates.current,
    )
    payments = PaymentService(
        store=store,
        gate=gate,
        agent_signer=agent,
        participant_signer=participant,
        bank=bank,
        closed_mandate_ttl_seconds=s.closed_mandate_ttl_seconds,
    )
    return Services(mandates=mandates, payments=payments)
