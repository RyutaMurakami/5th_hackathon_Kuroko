"""ローカル・テスト用の銀行アダプタ（呼ばれた回数を数える。bank-adapter を呼ばない）。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.clients.bank_adapter import BankAdapterError, TransferInfo


@dataclass
class FakeBankAdapter:
    authorized: set[str] | None = None  # None なら全員が認可済み
    fail_next: bool = False
    transfers: list[dict] = field(default_factory=list)

    def is_authorized(self, user_id: str) -> bool:
        return self.authorized is None or user_id in self.authorized

    def create_transfer(
        self, *, payer_user_id: str, payee_user_id: str, amount_yen: int, idempotency_key: str
    ) -> TransferInfo:
        if self.fail_next:
            self.fail_next = False
            raise BankAdapterError("bank_adapter_502")
        self.transfers.append(
            {
                "payer": payer_user_id,
                "payee": payee_user_id,
                "amount": amount_yen,
                "key": idempotency_key,
            }
        )
        return TransferInfo(
            transfer_id=f"tr-{len(self.transfers)}",
            status="awaiting_approval",
            approval_expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
