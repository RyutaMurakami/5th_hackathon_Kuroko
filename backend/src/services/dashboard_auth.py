"""Web ダッシュボードの利用者の確認（SPEC 4.3・7.6。TASKS B14）。**fail-closed**。

Cloud Run の ID トークン（`Authorization`。呼び出し元の SA）とは別に、
Firebase の ID トークンを `X-Firebase-Token` で受ける。
利用者の uid・メールは、署名検証済みのトークンから取る（自己申告ではない）。
- 許可リスト（`dashboard_users`）にあるメール → 幹事（organizer）
- それ以外の Google アカウント → ゲスト（guest）。キルスイッチ（`guest_enabled`）が切れていれば拒否
- 匿名認証は使わない。メールが未確認のトークンも拒否する
"""

from typing import Protocol

from fastapi import Header, HTTPException

from src.models.dashboard import Actor, Role
from src.services.container import get_event_store, get_firebase_verifier


class FirebaseVerifier(Protocol):
    def verify(self, token: str) -> dict:
        """署名・期限・aud・iss を検査した claims。不正なら例外（ValueError）。"""


class GoogleFirebaseVerifier:
    def __init__(self, project_id: str) -> None:
        self._project_id = project_id

    def verify(self, token: str) -> dict:
        if not self._project_id:
            raise ValueError("firebase_project_not_configured")  # 未設定は全て拒否
        from google.auth.transport import requests
        from google.oauth2 import id_token

        return id_token.verify_firebase_token(token, requests.Request(), audience=self._project_id)


def resolve_actor(verifier: FirebaseVerifier, token: str | None) -> Actor:
    """トークンから利用者を決める。決められなければ 401、ゲストが止められていれば 403。"""
    if not token:
        raise HTTPException(401, "unauthenticated")
    try:
        claims = verifier.verify(token)
    except Exception:  # 署名・期限・aud の不一致など。理由は返さない
        raise HTTPException(401, "unauthenticated") from None
    uid, email = claims.get("sub") or claims.get("user_id"), claims.get("email")
    provider = (claims.get("firebase") or {}).get("sign_in_provider")
    if not uid or not email or claims.get("email_verified") is not True:
        raise HTTPException(401, "unauthenticated")
    if provider == "anonymous":
        raise HTTPException(401, "unauthenticated")  # 匿名認証は使わない
    store = get_event_store()
    if store.dashboard_role(email) is not None:
        return Actor(uid=str(uid), email=email, role=Role.ORGANIZER)
    if not store.guest_enabled():
        raise HTTPException(403, "guest_disabled")  # 全体のキルスイッチ
    return Actor(uid=str(uid), email=email, role=Role.GUEST)


def current_actor(x_firebase_token: str | None = Header(default=None)) -> Actor:
    return resolve_actor(get_firebase_verifier(), x_firebase_token)
