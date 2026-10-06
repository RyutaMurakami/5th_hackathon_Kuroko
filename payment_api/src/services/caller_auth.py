"""呼び出し元の検査（ARCHITECTURE 6章）。

payment-api は非公開の Cloud Run で、ID トークンの署名は Cloud Run の IAM（invoker）が検証済み。
署名は再検証せず、クレーム（呼び出し元 SA と audience）だけを確かめる。
エージェントの identity は invoker に入っておらず、ここでも受け付けない（/mcp は B21）。
"""

from typing import Literal

from fastapi import Header, HTTPException
from google.auth import jwt

from src.config import get_settings

Caller = Literal["gateway", "api", "scheduler"]


def _email(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        claims = jwt.decode(authorization.removeprefix("Bearer "), verify=False)
    except ValueError:
        return None
    if claims.get("aud") != get_settings().payment_api_url or not claims.get("email_verified"):
        return None
    return claims.get("email")


def _caller(authorization: str | None, allowed: set[Caller]) -> Caller:
    s = get_settings()
    mapping: dict[str, Caller] = {}
    for sa, who in (
        (s.gateway_service_account, "gateway"),
        (s.api_service_account, "api"),
        (s.scheduler_service_account, "scheduler"),
    ):
        if sa:
            mapping[sa] = who  # type: ignore[assignment]
    who = mapping.get(_email(authorization) or "")
    if who is None or who not in allowed:
        raise HTTPException(status_code=403, detail="forbidden")
    return who


def require_gateway(authorization: str | None = Header(default=None)) -> Caller:
    """委任状の署名・取り消しは sa-gateway（署名検証済みの Slack 操作）だけ。"""
    return _caller(authorization, {"gateway"})


def require_api(authorization: str | None = Header(default=None)) -> Caller:
    """支払いの開始・参照は sa-api だけ。"""
    return _caller(authorization, {"api"})
