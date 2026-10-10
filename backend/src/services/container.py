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
def get_retro():
    from src.services.retrospective import Retrospectives

    return Retrospectives(
        store=get_event_store(), slack=_SlackClientPort(), extractor=_feedback_extractor()
    )


def get_extract_runner():
    """`extract-agent` の呼び出し口。エンジンが未設定（まだデプロイしていない）なら None。"""
    from src.clients.agent_runtime import AgentRuntimeClient
    from src.services.extract import AgentRuntimeExtractRunner

    s = get_settings()
    if not s.extract_agent_engine:
        return None
    location = s.extract_agent_engine.split("/locations/")[1].split("/")[0]
    client = AgentRuntimeClient(
        engine=s.extract_agent_engine, location=location, timeout=s.kuroko_agent_timeout_seconds
    )
    return AgentRuntimeExtractRunner(client)


def _feedback_extractor():
    from src.services.feedback_extract import AgentFeedbackExtractor, KeywordFeedbackExtractor

    runner = get_extract_runner()
    # エンジンが無いあいだは、キーワードの仮実装。あれば extract-agent（隔離抽出）を使う
    return AgentFeedbackExtractor(runner) if runner else KeywordFeedbackExtractor()


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
        retro=get_retro(),
    )


@lru_cache
def get_venue_search():
    from src.clients.ekispert import EkispertClient
    from src.clients.maps import MapsClient
    from src.services.venue_search import VenueSearch

    s = get_settings()
    return VenueSearch(
        store=get_event_store(),
        stations=EkispertClient(api_key=s.ekispert_api_key),
        maps=MapsClient(api_key=s.maps_api_key),
    )


def get_firebase_verifier():
    """Firebase の ID トークンの検証口。プロジェクトが未設定なら、全て拒否する。"""
    from src.services.dashboard_auth import GoogleFirebaseVerifier

    return GoogleFirebaseVerifier(get_settings().firebase_project_id)


class _TasksRsvpDispatcher:
    """出欠依頼（Slack）の投入。同じイベントは Cloud Tasks が重複として弾く。"""

    async def start_rsvp(self, event_id: str) -> None:
        from src.clients.cloud_tasks import enqueue_kuroko_api

        await enqueue_kuroko_api(
            "/tasks/internal/rsvp-requests", {"event_id": event_id}, f"rsvp-{event_id}"
        )


def get_dashboard():
    """Web ダッシュボードの操作（SPEC 4.3）。"""
    from src.clients.uploads import DisabledUploadSigner, GcsUploadSigner
    from src.services import kuroko_chat
    from src.services.dashboard import DashboardService
    from src.services.receipt_ocr import GeminiReceiptModel

    s = get_settings()
    signer = (
        GcsUploadSigner(bucket=s.upload_bucket, service_account_email=s.api_service_account)
        if s.upload_bucket
        else DisabledUploadSigner()
    )
    return DashboardService(
        store=get_event_store(),
        chat=kuroko_chat.reply,
        signer=signer,
        dispatcher=_TasksRsvpDispatcher(),
        upload_ttl_seconds=s.upload_url_ttl_seconds,
        ocr=GeminiReceiptModel(project=s.google_cloud_project) if s.google_cloud_project else None,
    )
