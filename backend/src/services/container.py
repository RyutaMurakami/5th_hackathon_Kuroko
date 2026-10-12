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
        lifecycle=get_lifecycle(),
        enqueue_self=_enqueue_self,
    )


async def _enqueue_self(path: str, payload: dict, task_id: str) -> None:
    from src.clients.cloud_tasks import enqueue_kuroko_api

    await enqueue_kuroko_api(path, payload, task_id)


@lru_cache
def get_memory():
    """記憶（Memory Bank）。エンジンが未設定なら、読まない・書けない（SPEC 9.8）。"""
    from src.clients.memory_bank import DisabledMemory, VertexMemoryBank

    s = get_settings()
    if not s.memory_bank_engine:
        return DisabledMemory()
    return VertexMemoryBank(engine=s.memory_bank_engine)


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
        store=get_event_store(),
        slack=_SlackClientPort(),
        extractor=_feedback_extractor(),
        memory=get_memory(),
        lifecycle=get_lifecycle(),
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
    from src.clients.cloud_tasks import enqueue_demo_mandate, enqueue_kuroko_api
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
        lifecycle=get_lifecycle(),
        proxy_sign=enqueue_demo_mandate if s.demo_runner_service_account else None,
        bank_approve=_approve_demo_transfer,
    )


async def _approve_demo_transfer(event_id: str, user_id: str) -> bool:
    """体験用の承認待ちの振込を、`bank-adapter` で承認済みにする（本物の振込には効かない）。"""
    transfer_id = _payment_reader().open_transfer_id(event_id, user_id)
    if not transfer_id:
        return False
    return await HttpBankAdapter(base_url=get_settings().bank_adapter_url).demo_approve(transfer_id)


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
        memory_store=get_memory(),
    )


@lru_cache
def get_preference_intake():
    """出欠のカードの入力欄（最寄り駅・苦手な食べ物）の取り込み（SPEC 7.7）。"""
    from src.clients.ekispert import EkispertClient
    from src.services.preferences import PreferenceIntake

    return PreferenceIntake(
        store=get_event_store(),
        runner=get_extract_runner(),  # 無ければ、語彙の語がそのまま書かれているかだけを見る
        stations=EkispertClient(api_key=get_settings().ekispert_api_key),
    )


def get_firebase_verifier():
    """Firebase の ID トークンの検証口。プロジェクトが未設定なら、全て拒否する。"""
    from src.services.dashboard_auth import GoogleFirebaseVerifier

    return GoogleFirebaseVerifier(get_settings().firebase_project_id)


class _TasksDispatcher:
    """Slack への依頼・按分の承認の投入。同じイベントは Cloud Tasks が重複として弾く。"""

    async def _enqueue(self, path: str, event_id: str, prefix: str) -> None:
        from src.clients.cloud_tasks import enqueue_kuroko_api

        await enqueue_kuroko_api(path, {"event_id": event_id}, f"{prefix}-{event_id}")

    async def start_rsvp(self, event_id: str) -> None:
        await self._enqueue("/tasks/internal/rsvp-requests", event_id, "rsvp")

    async def start_budget_request(self, event_id: str) -> None:
        await self._enqueue("/tasks/internal/budget-requests", event_id, "budget")

    async def start_split_approval(self, event_id: str) -> None:
        await self._enqueue("/tasks/internal/approval-requests", event_id, "approval")

    async def start_checkouts(self, event_id: str, split_hash: str) -> None:
        """幹事が振込の依頼を送ることを承認したあと、請求を作る（同じ金額表は1回だけ）。"""
        from src.clients.cloud_tasks import enqueue_kuroko_api

        await enqueue_kuroko_api(
            "/tasks/internal/checkouts", {"event_id": event_id},
            f"checkout-{event_id}-{split_hash[:16]}",
        )  # fmt: skip


def get_dashboard():
    """Web ダッシュボードの操作（SPEC 4.3）。"""
    from src.clients.uploads import DisabledUploadSigner, GcsUploadSigner
    from src.services import kuroko_chat
    from src.services.dashboard import DashboardService
    from src.services.policy_extract import GeminiPolicyModel, PolicyReader
    from src.services.receipt_ocr import GeminiReceiptModel
    from src.services.reservation_read import GeminiReservationModel

    s = get_settings()
    project = s.google_cloud_project
    signer = (
        GcsUploadSigner(bucket=s.upload_bucket, service_account_email=s.api_service_account)
        if s.upload_bucket
        else DisabledUploadSigner()
    )
    return DashboardService(
        store=get_event_store(),
        chat=kuroko_chat.reply,
        signer=signer,
        dispatcher=_TasksDispatcher(),
        lifecycle=get_lifecycle(),
        payments=_payment_reader(),
        personas=get_slack_actions(),
        retro=get_retro(),
        venues=get_venue_search(),
        # 返答は Cloud Tasks で作る（Hosting の60秒制限。SPEC 7.5）。ローカルでは、その場で待つ
        enqueue_chat=_enqueue_self if project and s.kuroko_api_url else None,
        prefs=get_preference_intake(),
        upload_ttl_seconds=s.upload_url_ttl_seconds,
        ocr=GeminiReceiptModel(project=project) if project else None,
        reservation_reader=GeminiReservationModel(project=project) if project else None,
        # 規程は、文書から読み取って検証する（プロジェクトが無いローカルでは、既定の値）
        policy=PolicyReader(model=GeminiPolicyModel(project=project) if project else None),
    )


@lru_cache
def get_lifecycle():
    from src.services.lifecycle import Lifecycle

    return Lifecycle(store=get_event_store())


def _payment_reader() -> PaymentReader:
    s = get_settings()
    if s.google_cloud_project:
        return FirestorePaymentReader(
            project=s.google_cloud_project, database=s.firestore_database_id
        )
    return MemoryPaymentReader()
