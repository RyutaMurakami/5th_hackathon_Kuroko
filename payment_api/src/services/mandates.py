"""委任状（AP2 の Open Payment Mandate）の署名・取り消し・取得（SPEC 8.4）。

参加者の署名鍵は MVP ではサーバー側（KMS の1つの鍵）で管理する（SPEC 10章）。人ごとの区別は、
署名の `kid`（`user:<user_id>`）と、署名つきの委任状の中身（`payment_instrument` に本人、
`risk_data` にイベントID）で行う。本番では本人の端末（パスキーなど）に鍵を置く。
"""

import base64
import json
from collections.abc import Callable
from datetime import UTC, datetime

from ap2.sdk.generated.open_payment_mandate import (
    AllowedPayees,
    AmountRange,
    OpenPaymentMandate,
)
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient

from src.clients.signers import MandateSigner
from src.db.store import Store
from src.models.schemas import MandateResponse, MandateStatus, SignMandateRequest

CURRENCY = "JPY"
INSTRUMENT_TYPE = "bank_transfer"
AGENT_KID = "payment-agent"


class MandateConflict(Exception):
    """既に署名済み（取り消し・期限切れ・使用済みを含む）。同じ内容の再送は成功として返す。"""


class UnknownMandate(Exception):
    pass


class PaymentAlreadyStarted(Exception):
    """振込依頼が作られたあとは取り消せない（SPEC 8.7）。"""


class InvalidMandate(Exception):
    pass


def mandate_id_for(event_id: str, user_id: str) -> str:
    return f"{event_id}:{user_id}"


def participant_kid(user_id: str) -> str:
    return f"user:{user_id}"


def token_kid(token: str) -> str | None:
    """SD-JWT の先頭（発行者の JWS）のヘッダーから kid を読む。署名の検証は SDK が行う。"""
    try:
        header = token.split("~")[0].split(".")[0]
        header += "=" * (-len(header) % 4)
        return json.loads(base64.urlsafe_b64decode(header)).get("kid")
    except (ValueError, IndexError):
        return None


class MandateService:
    def __init__(
        self,
        *,
        store: Store,
        participant_signer: MandateSigner,
        agent_signer: MandateSigner,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._participant = participant_signer
        self._agent = agent_signer
        self._now = now
        self._client = MandateClient()

    def sign(self, req: SignMandateRequest) -> MandateResponse:
        now = self._now()
        if req.expires_at <= now or req.expires_at.tzinfo is None:
            raise InvalidMandate
        if req.payee_user_id == req.user_id:
            raise InvalidMandate  # 自分宛ての委任は作らない（幹事本人は振込をしない）
        mandate_id = mandate_id_for(req.event_id, req.user_id)
        existing = self.current(mandate_id)
        if existing is not None:
            same = (
                existing["status"] == MandateStatus.ACTIVE.value
                and existing["payee_user_id"] == req.payee_user_id
                and existing["cap_yen"] == req.cap_yen
            )
            if same:
                return self._response(existing)  # Cloud Tasks の再送などでの二重署名を防ぐ
            raise MandateConflict

        payee = Merchant(id=req.payee_user_id, name=req.payee_user_id)
        open_mandate = OpenPaymentMandate(
            constraints=[
                AmountRange(currency=CURRENCY, min=0, max=req.cap_yen),
                AllowedPayees(allowed=[payee]),
            ],
            payment_instrument=PaymentInstrument(id=req.user_id, type=INSTRUMENT_TYPE),
            risk_data={"event_id": req.event_id},
            cnf={"jwk": self._agent.public_key().export_public(as_dict=True)},
            iat=int(now.timestamp()),
            exp=int(req.expires_at.timestamp()),
        )
        token = self._client.create(
            payloads=[open_mandate],
            issuer_key=self._participant.signing_key(participant_kid(req.user_id)),
        )
        record = {
            "mandate_id": mandate_id,
            "event_id": req.event_id,
            "user_id": req.user_id,
            "payee_user_id": req.payee_user_id,
            "cap_yen": req.cap_yen,
            "open_payment_mandate": token,
            "status": MandateStatus.ACTIVE.value,
            "signed_at": now,
            "expires_at": req.expires_at,
            "revoked_at": None,
            "signed_via": req.signed_via,
        }
        self._store.put_mandate(mandate_id, record)
        return self._response(record)

    def revoke(self, mandate_id: str) -> MandateResponse:
        record = self.current(mandate_id)
        if record is None:
            raise UnknownMandate
        if record["status"] == MandateStatus.REVOKED.value:
            return self._response(record)
        if self._store.find_open_payment(record["event_id"], record["user_id"]) is not None:
            raise PaymentAlreadyStarted
        record = self._store.update_mandate(
            mandate_id,
            {"status": MandateStatus.REVOKED.value, "revoked_at": self._now()},
        )
        return self._response(record)

    def get(self, mandate_id: str) -> MandateResponse:
        record = self.current(mandate_id)
        if record is None:
            raise UnknownMandate
        return self._response(record)

    def current(self, mandate_id: str) -> dict | None:
        """期限を過ぎた委任状は、読むときに expired にする。"""
        record = self._store.get_mandate(mandate_id)
        if (
            record
            and record["status"] == MandateStatus.ACTIVE.value
            and self._now() >= record["expires_at"]
        ):
            record = self._store.update_mandate(mandate_id, {"status": MandateStatus.EXPIRED.value})
        return record

    @staticmethod
    def _response(record: dict) -> MandateResponse:
        return MandateResponse(
            mandate_id=record["mandate_id"],
            event_id=record["event_id"],
            user_id=record["user_id"],
            payee_user_id=record["payee_user_id"],
            cap_yen=record["cap_yen"],
            status=MandateStatus(record["status"]),
            signed_at=record["signed_at"],
            expires_at=record["expires_at"],
            revoked_at=record.get("revoked_at"),
        )
