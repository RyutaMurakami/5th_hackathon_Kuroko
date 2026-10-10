"""請求（Checkout）の署名（AP2 の Merchant 役。ARCHITECTURE 4.2・SPEC 8.4）。

ES256 の JWT。本番は Cloud KMS の `claim-signing`（署名できるのは sa-api だけ。秘密鍵は KMS の外に
出ない）。署名の形式は `payment_api/src/services/checkout.py` の検証と対になっている。
"""

import base64
import hashlib
import json
from typing import Any, Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _raw_signature(der: bytes) -> bytes:
    r, s = decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


class ClaimSigner(Protocol):
    def sign(self, claims: dict[str, Any]) -> str:
        """claims に署名した JWT（ES256）を返す。"""


class LocalClaimSigner:
    """テスト・ローカル用。鍵はプロセス内。"""

    def __init__(self, key: ec.EllipticCurvePrivateKey | None = None) -> None:
        self._key = key or ec.generate_private_key(ec.SECP256R1())

    @property
    def public_key(self) -> ec.EllipticCurvePublicKey:
        return self._key.public_key()

    def sign(self, claims: dict[str, Any]) -> str:
        head = _b64(json.dumps({"alg": "ES256", "typ": "JWT", "kid": "claim-signing"}).encode())
        body = _b64(json.dumps(claims, separators=(",", ":")).encode())
        der = self._key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256()))
        return f"{head}.{body}.{_b64(_raw_signature(der))}"


class KmsClaimSigner:
    def __init__(self, *, version_name: str, kms_client: Any | None = None) -> None:
        if kms_client is None:
            from google.cloud import kms

            kms_client = kms.KeyManagementServiceClient()
        self._kms, self._name = kms_client, version_name

    def sign(self, claims: dict[str, Any]) -> str:
        head = _b64(json.dumps({"alg": "ES256", "typ": "JWT", "kid": "claim-signing"}).encode())
        body = _b64(json.dumps(claims, separators=(",", ":")).encode())
        digest = hashlib.sha256(f"{head}.{body}".encode()).digest()
        res = self._kms.asymmetric_sign(request={"name": self._name, "digest": {"sha256": digest}})
        return f"{head}.{body}.{_b64(_raw_signature(res.signature))}"
