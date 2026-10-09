"""設定から請求・入金確認のサービスを組み立てる（保存先・署名鍵・外部呼び出しを設定で切り替える）。"""

from functools import lru_cache

from src.clients.bank_adapter import HttpBankAdapter
from src.clients.claim_signer import ClaimSigner, KmsClaimSigner, LocalClaimSigner
from src.clients.payment_api import HttpPaymentApi
from src.config import get_settings
from src.db.events import EventStore, FirestoreEventStore, MemoryEventStore
from src.db.payments import FirestorePaymentReader, MemoryPaymentReader, PaymentReader
from src.services.billing import BillingService


@lru_cache
def get_event_store() -> EventStore:
    s = get_settings()
    if not s.google_cloud_project:  # ローカル（プロジェクトなし）だけ、メモリに置く
        return MemoryEventStore()
    return FirestoreEventStore(project=s.google_cloud_project, database=s.firestore_database_id)


@lru_cache
def get_billing() -> BillingService:
    s = get_settings()
    signer: ClaimSigner = (
        KmsClaimSigner(version_name=s.kms_claim_key_version)
        if s.kms_claim_key_version
        else LocalClaimSigner()  # 鍵の設定が無いと、payment-api が検証できず請求は通らない
    )
    payments: PaymentReader = (
        FirestorePaymentReader(project=s.google_cloud_project, database=s.firestore_database_id)
        if s.google_cloud_project
        else MemoryPaymentReader()
    )
    return BillingService(
        store=get_event_store(),
        signer=signer,
        payment_api=HttpPaymentApi(base_url=s.payment_api_url),
        bank=HttpBankAdapter(base_url=s.bank_adapter_url),
        payments=payments,
        checkout_ttl_seconds=s.checkout_ttl_seconds,
    )


class _SlackClientPort:
    """`clients/slack.py` を SlackPort の形に包む（kuroko-api だけが Bot Token を持つ）。"""

    async def post_dm(self, slack_user_id: str, text: str, blocks: list[dict]) -> None:
        from src.clients import slack

        await slack.post_dm(slack_user_id, text, blocks)

    async def respond(self, response_url: str, text: str, blocks: list[dict]) -> None:
        from src.clients import slack

        await slack.respond(response_url, text, blocks)

    async def publish_home(self, slack_user_id: str, view: dict) -> None:
        from src.clients import slack

        await slack.publish_home(slack_user_id, view)


@lru_cache
def get_slack_actions():
    from src.clients.cloud_tasks import enqueue_kuroko_api
    from src.db.mandates import FirestoreMandateReader, MemoryMandateReader
    from src.services.slack_actions import SlackActions

    s = get_settings()
    mandates = (
        FirestoreMandateReader(project=s.google_cloud_project, database=s.firestore_database_id)
        if s.google_cloud_project
        else MemoryMandateReader()
    )
    return SlackActions(
        store=get_event_store(),
        slack=_SlackClientPort(),
        enqueue_self=enqueue_kuroko_api,
        mandates=mandates,
    )
