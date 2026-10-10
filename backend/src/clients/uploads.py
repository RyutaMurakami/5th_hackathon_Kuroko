"""予約画面・領収書の Cloud Storage への署名付き URL（SPEC 7.5。TASKS B14）。

ブラウザが署名付き URL に直接アップロードする（kuroko-api を経由しない）。URL は短い期限・
Content-Type 固定の PUT だけ。署名は Cloud Run のサービスアカウントの IAM で行う（鍵ファイルなし）。
"""

import datetime as dt

import google.auth
from google.auth.transport import requests
from google.cloud import storage


class GcsUploadSigner:
    def __init__(self, *, bucket: str, service_account_email: str) -> None:
        self._bucket, self._sa = bucket, service_account_email
        self._client = storage.Client()

    def signed_put_url(self, path: str, content_type: str, ttl_seconds: int) -> str:
        creds, _ = google.auth.default()
        creds.refresh(requests.Request())
        blob = self._client.bucket(self._bucket).blob(path)
        return blob.generate_signed_url(
            version="v4",
            method="PUT",
            expiration=dt.timedelta(seconds=ttl_seconds),
            content_type=content_type,
            service_account_email=self._sa,
            access_token=creds.token,
        )

    def read_bytes(self, path: str) -> bytes | None:
        blob = self._client.bucket(self._bucket).get_blob(path)
        return blob.download_as_bytes() if blob is not None else None

    def object_size(self, path: str) -> int | None:
        blob = self._client.bucket(self._bucket).get_blob(path)
        return blob.size if blob is not None else None


class DisabledUploadSigner:
    """バケット未設定のあいだ。アップロードは受け付けない。"""

    def signed_put_url(self, path: str, content_type: str, ttl_seconds: int) -> str:
        raise RuntimeError("uploads_not_configured")

    def read_bytes(self, path: str) -> bytes | None:
        return None

    def object_size(self, path: str) -> int | None:
        return None
