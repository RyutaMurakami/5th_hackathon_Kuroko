"""呼び出し元の検査（ARCHITECTURE 6章）。

bank-adapter は非公開の Cloud Run で、ID トークンの署名は Cloud Run の IAM（invoker）が検証済み。
Cloud Run は署名を外して渡すので、ここでは署名を再検証せず、
クレーム（呼び出し元 SA と audience）だけを確かめる。
エージェントの identity は invoker に入っておらず、ここでも受け付けない。
"""

from typing import Literal

from fastapi import Header, HTTPException
from google.auth import jwt

from src.config import get_settings

Caller = Literal["api", "payment"]


def _caller_email(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        claims = jwt.decode(authorization.removeprefix("Bearer "), verify=False)
    except ValueError:
        return None
    if claims.get("aud") != get_settings().bank_adapter_url or not claims.get("email_verified"):
        return None
    return claims.get("email")


def _caller(authorization: str | None, allowed: set[Caller]) -> Caller:
    s = get_settings()
    email = _caller_email(authorization)
    mapping: dict[str, Caller] = {}
    if s.api_service_account:
        mapping[s.api_service_account] = "api"
    if s.payment_api_service_account:
        mapping[s.payment_api_service_account] = "payment"
    who = mapping.get(email or "")
    if who is None or who not in allowed:
        raise HTTPException(status_code=403, detail="forbidden")
    return who


def require_payment(authorization: str | None = Header(default=None)) -> Caller:
    """振込の依頼・状況・認可は sa-payment-api だけ。"""
    return _caller(authorization, {"payment"})


def require_api_or_payment(authorization: str | None = Header(default=None)) -> Caller:
    """明細（sa-api: 幹事の入金。sa-payment-api: 本人の出金）と削除。"""
    return _caller(authorization, {"api", "payment"})


def require_api(authorization: str | None = Header(default=None)) -> Caller:
    """体験用の「銀行で承認する」は sa-api だけ（Web のカードの操作を受けた kuroko-api）。"""
    return _caller(authorization, {"api"})
