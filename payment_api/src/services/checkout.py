"""請求（Checkout）の検査。KUROKO（請求側）が署名した請求と按分表のハッシュ値の検証（B13）。

請求側の署名の実装は B13（kuroko-api の `create_checkout`）。それまでは検証器を差し替え式にし、
本番では未設定のあいだ**すべて拒否**する（お金に関わる検査は通らなければ進めない）。
"""

from typing import Protocol


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
    """請求側の署名の検証が未実装（B13）のあいだの既定。fail closed。"""

    def verify(self, **_: object) -> bool:
        return False


class AcceptAllCheckouts:
    """ローカル・テスト専用。本番では使わない。"""

    def verify(self, **_: object) -> bool:
        return True
