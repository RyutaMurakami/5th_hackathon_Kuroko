"""KMS 署名の差し込みが、AP2 SDK でそのまま動く（KMS はテスト用の偽物。実機は B12 で確認）。"""

import time
from types import SimpleNamespace

from ap2.sdk.generated.open_payment_mandate import AllowedPayees, AmountRange, OpenPaymentMandate
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.mandate import MandateClient
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.clients.signers import KmsSigner, LocalSigner


class FakeKms:
    """KMS の AsymmetricSign / GetPublicKey の形だけを模す。秘密鍵はここから外に出ない。"""

    def __init__(self) -> None:
        self._key = ec.generate_private_key(ec.SECP256R1())
        self.sign_calls = 0

    def get_public_key(self, request):
        pem = self._key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return SimpleNamespace(pem=pem.decode())

    def asymmetric_sign(self, request):
        self.sign_calls += 1
        digest = request["digest"]["sha256"]
        from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

        sig = self._key.sign(digest, ec.ECDSA(Prehashed(hashes.SHA256())))
        return SimpleNamespace(signature=sig)


def _open(agent_pub: dict) -> OpenPaymentMandate:
    now = int(time.time())
    return OpenPaymentMandate(
        constraints=[
            AmountRange(currency="JPY", min=0, max=5000),
            AllowedPayees(allowed=[Merchant(id="organizer", name="organizer")]),
        ],
        cnf={"jwk": agent_pub},
        iat=now,
        exp=now + 3600,
    )


def test_kms_signer_signs_through_kms_and_verifies_with_public_key_only():
    kms = FakeKms()
    signer = KmsSigner(version_name="projects/p/.../cryptoKeyVersions/1", kms_client=kms)
    agent_pub = LocalSigner().public_key().export_public(as_dict=True)
    client = MandateClient()
    token = client.create(payloads=[_open(agent_pub)], issuer_key=signer.signing_key("user:member"))
    assert kms.sign_calls == 1  # 署名は KMS が行った
    result = client.verify(
        token=token, key_or_provider=signer.public_key(), payload_type=OpenPaymentMandate
    )  # 時計は実際の時刻（このテストは SDK だけを使う）
    assert result.mandate_payload.constraints[0].max == 5000


def test_kid_is_per_user_with_one_key():
    kms = FakeKms()
    signer = KmsSigner(version_name="v", kms_client=kms)
    assert signer.signing_key("user:a").kid == "user:a"
    assert signer.signing_key("user:b").kid == "user:b"
    assert signer.public_key().export_public(as_dict=True)["kty"] == "EC"
