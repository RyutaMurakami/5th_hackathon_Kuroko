"""請求（Checkout）の署名の検証（SPEC 6.3: 請求に有効な署名があり、按分表のハッシュを含む）。"""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from src.services.checkout import ApprovedSplit, RejectAllCheckouts, SignedCheckoutVerifier

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
KEY = ec.generate_private_key(ec.SECP256R1())


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign(claims: dict, key=KEY, alg="ES256") -> str:
    """`kuroko-api` の署名と同じ形（ES256。署名は r||s の64バイト）。"""
    head = b64(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    body = b64(json.dumps(claims).encode())
    der = key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return f"{head}.{body}.{b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def claims(**kw) -> dict:
    return {
        "iss": "kuroko-api",
        "aud": "payment-api",
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(days=3)).timestamp()),
        "sub": "ito",
        "payee": "takahashi",
        "event_id": "ev1",
        "payment_reference": "ev1",
        "amount_yen": 3300,
        "currency": "JPY",
        "split_hash": "split-hash-1",
        "jti": "c1",
    } | kw


class Approved:
    def __init__(self, approved=None):
        self.value = (
            approved
            if approved is not None
            else ApprovedSplit(
                "split-hash-1", {"ito": 3300, "yamada": 7200, "takahashi": 3300}, "takahashi"
            )
        )

    def approved_split(self, event_id):
        return self.value if event_id == "ev1" else None


def verifier(approved=None, key=None, now=NOW):
    key = key or KEY.public_key()
    return SignedCheckoutVerifier(public_key=key, approved=Approved(approved), now=lambda: now)


def call(v, token=None, **kw):
    token = token if token is not None else sign(claims())
    args = {
        "checkout_jwt": token,
        "checkout_hash": hashlib.sha256(token.encode()).hexdigest(),
        "event_id": "ev1",
        "payer_user_id": "ito",
        "payee_user_id": "takahashi",
        "amount_yen": 3300,
    } | kw
    return v.verify(**args)


def test_valid_checkout_passes():
    assert call(verifier())


@pytest.mark.parametrize(
    "kw",
    [
        {"payer_user_id": "sasaki"},  # 請求の相手と違う人の支払い
        {"payee_user_id": "attacker"},  # 支払先の差し替え
        {"amount_yen": 3400},  # 金額の差し替え
        {"event_id": "ev2"},  # 別イベント
        {"checkout_hash": "0" * 64},  # ハッシュの使い回し・差し替え
    ],
)
def test_request_that_differs_from_the_signed_checkout_is_rejected(kw):
    assert not call(verifier(), **kw)


@pytest.mark.parametrize(
    "bad",
    [
        {"iss": "someone"},
        {"aud": "bank-adapter"},
        {"exp": int((NOW - timedelta(seconds=1)).timestamp())},  # 期限切れ
        {"iat": int((NOW + timedelta(hours=1)).timestamp())},  # 未来の発行
        {"currency": "USD"},
        {"payment_reference": "ev2"},
        {"split_hash": ""},  # 按分表のハッシュを含まない
    ],
)
def test_signed_but_invalid_claims_are_rejected(bad):
    assert not call(verifier(), token=sign(claims(**bad)))


def test_missing_claims_are_rejected():
    c = claims()
    del c["split_hash"]
    assert not call(verifier(), token=sign(c))


def test_signature_by_another_key_or_algorithm_is_rejected():
    forged = sign(claims(), key=ec.generate_private_key(ec.SECP256R1()))
    assert not call(verifier(), token=forged)
    assert not call(verifier(), token=sign(claims(), alg="none"))
    tampered = sign(claims())
    head, body, sig = tampered.split(".")
    body = b64(json.dumps(claims(amount_yen=1)).encode())
    assert not call(verifier(), token=f"{head}.{body}.{sig}")
    for junk in ("", "a.b", "a.b.c", "x" * 10):
        assert not call(
            verifier(), token=junk, checkout_hash=hashlib.sha256(junk.encode()).hexdigest()
        )


def test_must_match_the_approved_split():
    v = SignedCheckoutVerifier(
        public_key=KEY.public_key(),
        approved=type("N", (), {"approved_split": lambda self, e: None})(),
        now=lambda: NOW,
    )
    assert not call(v)  # 承認されていない・金額表がない
    stale = ApprovedSplit("other-hash", {"ito": 3300}, "takahashi")
    assert not call(verifier(approved=stale))  # 承認された按分表のハッシュと違う
    other_amount = ApprovedSplit("split-hash-1", {"ito": 3200}, "takahashi")
    assert not call(verifier(approved=other_amount))  # 金額表の本人の負担額と違う
    other_organizer = ApprovedSplit("split-hash-1", {"ito": 3300}, "somebody")
    assert not call(verifier(approved=other_organizer))  # 支払先が幹事でない
    no_row = ApprovedSplit("split-hash-1", {}, "takahashi")
    assert not call(verifier(approved=no_row))  # 金額表に載っていない人


def test_organizer_can_never_be_a_payer():
    token = sign(claims(sub="takahashi", payee="takahashi"))
    v = verifier(approved=ApprovedSplit("split-hash-1", {"takahashi": 3300}, "takahashi"))
    assert not call(v, token=token, payer_user_id="takahashi")


def test_reject_all_is_the_fail_closed_default():
    assert not call(RejectAllCheckouts())
