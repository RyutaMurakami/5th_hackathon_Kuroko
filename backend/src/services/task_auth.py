"""/tasks/* の呼び出し元の検査（ARCHITECTURE 6章。ルート単位の絞り込みはアプリ層で行う）。

kuroko-api は非公開の Cloud Run で、ID トークンの署名は Cloud Run の IAM（invoker）が検証済み。
Cloud Run はコンテナに渡すときに署名を外すため、ここでは署名を再検証せず、クレーム（呼び出し元 SA と
audience）だけを確かめる。
"""

from fastapi import Header, HTTPException
from google.auth import jwt

from src.config import get_settings


def caller_email(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        claims = jwt.decode(authorization.removeprefix("Bearer "), verify=False)
    except ValueError:
        return None
    if claims.get("aud") != get_settings().kuroko_api_url or not claims.get("email_verified"):
        return None
    return claims.get("email")


def require_gateway(authorization: str | None = Header(default=None)) -> None:
    """`/tasks/slack/*` は sa-gateway（署名検証済みの Slack 由来の操作）だけを受け付ける。"""
    expected = get_settings().gateway_service_account
    if not expected or caller_email(authorization) != expected:
        raise HTTPException(status_code=403, detail="forbidden")


def require_self(authorization: str | None = Header(default=None)) -> None:
    """`/tasks/internal/*` は kuroko-api 自身（sa-api。Cloud Tasks が投入）だけを受け付ける。"""
    expected = get_settings().api_service_account
    if not expected or caller_email(authorization) != expected:
        raise HTTPException(status_code=403, detail="forbidden")


def require_dashboard(authorization: str | None = Header(default=None)) -> None:
    """`/api/dashboard/*` は kuroko-dashboard（sa-dashboard）だけを受け付ける。"""
    expected = get_settings().dashboard_service_account
    if not expected or caller_email(authorization) != expected:
        raise HTTPException(status_code=403, detail="forbidden")


def require_scheduler(authorization: str | None = Header(default=None)) -> None:
    """`/tasks/scheduled/*` は sa-scheduler（Cloud Scheduler）だけを受け付ける。"""
    expected = get_settings().scheduler_service_account
    if not expected or caller_email(authorization) != expected:
        raise HTTPException(status_code=403, detail="forbidden")
