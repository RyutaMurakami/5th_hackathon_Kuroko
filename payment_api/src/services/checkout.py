"""請求（Checkout）の検査。`kuroko-api`（請求側）が署名した請求の検証（SPEC 6.3・TASKS B13）。

請求は ES256 の JWT（鍵は Cloud KMS の `claim-signing`。署名できるのは `sa-api` だけ）。
`payment-api` は、請求側を信用しすぎないために、次を**自分で**確かめる:
- 署名（KMS の公開鍵）・有効期限・宛先（aud）
- 請求の中身（イベント・支払う人・支払先・金額）が、依頼の内容と一致する
- 請求の按分表のハッシュ値が、**承認済みの按分表**（Firestore。`kuroko-api` が書く）と一致し、
  その表の本人の負担額・幹事（支払先）と矛盾しない
- 請求のハッシュ値 = JWT の SHA-256（`checkout_hash` を差し替えて使い回せない）
"""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

ISSUER = "kuroko-api"
AUDIENCE = "payment-api"
CURRENCY = "JPY"
CLOCK_SKEW_SECONDS = 60


class CheckoutVerifier(Protocol):
    def verify(
        self,
        *,
        checkout_jwt: str,
        checkout_hash: str,
        event_id: str,
        payer_user_id: str,
        payee_user_id: str,
        amount_yen: int,
    ) -> bool: ...


class RejectAllCheckouts:
    """請求側の署名の検証が設定されていないときの既定。fail closed。"""

    def verify(self, **_: object) -> bool:
        return False


class AcceptAllCheckouts:
    """ローカル・テスト専用。本番では使わない。"""

    def verify(self, **_: object) -> bool:
        return True


@dataclass(frozen=True)
class ApprovedSplit:
    split_hash: str
    shares: dict[str, int]  # user_id → 負担額
    organizer_user_id: str


class ApprovedSplitLookup(Protocol):
    def approved_split(self, event_id: str) -> ApprovedSplit | None:
        """承認済みの按分表。承認がない・金額表がない・両者のハッシュが違うなら None。"""


class FirestoreApprovedSplits:
    """`kuroko-api` が書く events/{id}・approvals・splits を読む（読み取りだけ）。"""

    def __init__(self, *, project: str, database: str) -> None:
        from google.cloud import firestore

        self._db = firestore.Client(project=project or None, database=database)

    def approved_split(self, event_id: str) -> ApprovedSplit | None:
        event = self._db.collection("events").document(event_id)
        ev, ap, sp = (
            event.get(),
            event.collection("approvals").document("current").get(),
            event.collection("splits").document("current").get(),
        )
        if not (ev.exists and ap.exists and sp.exists):
            return None
        approval, split = ap.to_dict(), sp.to_dict()
        if approval.get("status") != "approved" or approval.get("split_hash") != split.get("hash"):
            return None
        return ApprovedSplit(
            split_hash=split["hash"],
            shares={r["user_id"]: int(r["share_yen"]) for r in split.get("rows", [])},
            organizer_user_id=ev.to_dict()["organizer_user_id"],
        )


def _b64url_decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def decode_checkout(token: str, public_key: ec.EllipticCurvePublicKey) -> dict[str, Any] | None:
    """署名が正しければ、中身（claims）を返す。形式・署名が不正なら None。"""
    try:
        head_b64, body_b64, sig_b64 = token.split(".")
        header = json.loads(_b64url_decode(head_b64))
        if header.get("alg") != "ES256":
            return None
        raw = _b64url_decode(sig_b64)
        if len(raw) != 64:
            return None
        der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
        public_key.verify(der, f"{head_b64}.{body_b64}".encode(), ec.ECDSA(hashes.SHA256()))
        return json.loads(_b64url_decode(body_b64))
    except (ValueError, InvalidSignature, KeyError):
        return None


class SignedCheckoutVerifier:
    def __init__(
        self,
        *,
        public_key: ec.EllipticCurvePublicKey,
        approved: ApprovedSplitLookup,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._key, self._approved, self._now = public_key, approved, now

    def verify(
        self,
        *,
        checkout_jwt: str,
        checkout_hash: str,
        event_id: str,
        payer_user_id: str,
        payee_user_id: str,
        amount_yen: int,
    ) -> bool:
        if hashlib.sha256(checkout_jwt.encode()).hexdigest() != checkout_hash:
            return False
        claims = decode_checkout(checkout_jwt, self._key)
        if claims is None:
            return False
        ts = int(self._now().timestamp())
        try:
            if (
                claims["iss"] != ISSUER
                or claims["aud"] != AUDIENCE
                or int(claims["exp"]) <= ts
                or int(claims["iat"]) > ts + CLOCK_SKEW_SECONDS
                or claims["currency"] != CURRENCY
                or claims["event_id"] != event_id
                or claims["payment_reference"] != event_id
                or claims["sub"] != payer_user_id
                or claims["payee"] != payee_user_id
                or int(claims["amount_yen"]) != amount_yen
                or not claims["split_hash"]
            ):
                return False
        except (KeyError, TypeError, ValueError):
            return False
        approved = self._approved.approved_split(event_id)
        return (
            approved is not None
            and claims["split_hash"] == approved.split_hash
            and payee_user_id == approved.organizer_user_id
            and payer_user_id != approved.organizer_user_id
            and approved.shares.get(payer_user_id) == amount_yen
            and amount_yen > 0
        )
