"""AP2 の署名鍵（ES256。P-256）。

AP2 SDK は jwcrypto の JWK で署名する。テストでは JWK をそのまま使い、本番では署名の瞬間だけ
Cloud KMS の AsymmetricSign を呼ぶ JWK（`_KmsJWK`）を差し込む。秘密鍵は KMS の外に出ない。
"""

import hashlib
from typing import Any, Protocol

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK


class MandateSigner(Protocol):
    def signing_key(self, kid: str) -> JWK:
        """署名に使う JWK（kid つき）。SDK の `create` / `present` に渡す。"""

    def public_key(self) -> JWK:
        """検証に使う公開鍵。"""


class LocalSigner:
    """テスト用。鍵はプロセス内で作る（本番・デモでは使わない）。"""

    def __init__(self) -> None:
        self._key = ec.generate_private_key(ec.SECP256R1())

    def signing_key(self, kid: str) -> JWK:
        d = JWK.from_pyca(self._key).export(as_dict=True)
        d["kid"] = kid
        return JWK(**d)

    def public_key(self) -> JWK:
        return JWK.from_pyca(self._key.public_key())


class _RemoteEcKey:
    """pyca の EC 秘密鍵の代わり。sign() だけを KMS に任せる。"""

    key_size = 256
    curve = ec.SECP256R1()

    def __init__(self, kms: Any, version_name: str, public: ec.EllipticCurvePublicKey) -> None:
        self._kms, self._name, self._public = kms, version_name, public

    def sign(self, data: bytes, algorithm: ec.ECDSA) -> bytes:
        if not isinstance(algorithm.algorithm, hashes.SHA256):
            raise ValueError("ES256 only")
        digest = hashlib.sha256(data).digest()
        res = self._kms.asymmetric_sign(request={"name": self._name, "digest": {"sha256": digest}})
        return res.signature  # DER。jwcrypto が r||s に直す

    def public_key(self) -> ec.EllipticCurvePublicKey:
        return self._public


class _KmsJWK(JWK):
    """公開鍵の情報だけを持ち、署名のときだけ KMS を呼ぶ JWK。"""

    _remote: _RemoteEcKey

    def get_op_key(self, operation=None, arg=None):  # noqa: ANN001, ANN201
        if operation == "sign":
            return self._remote
        return super().get_op_key(operation, arg)


class KmsSigner:
    def __init__(self, *, version_name: str, kms_client: Any | None = None) -> None:
        if kms_client is None:
            from google.cloud import kms

            kms_client = kms.KeyManagementServiceClient()
        self._kms, self._name = kms_client, version_name
        pem = kms_client.get_public_key(request={"name": version_name}).pem
        self._public = serialization.load_pem_public_key(pem.encode())
        if not isinstance(self._public, ec.EllipticCurvePublicKey):
            raise ValueError("KMS key must be an EC key (EC_SIGN_P256_SHA256)")

    def signing_key(self, kid: str) -> JWK:
        pub = JWK.from_pyca(self._public).export_public(as_dict=True)
        key = _KmsJWK(**pub, kid=kid)
        key._remote = _RemoteEcKey(self._kms, self._name, self._public)
        return key

    def public_key(self) -> JWK:
        return JWK.from_pyca(self._public)
