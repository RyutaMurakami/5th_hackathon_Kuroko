"""ローカル・テスト用の銀行アダプタ（呼ばれた回数を数える。bank-adapter を呼ばない）。"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from src.clients.bank_adapter import BankAdapterError, OutgoingEntry, TransferInfo


@dataclass
class FakeBankAdapter:
    authorized: set[str] | None = None  # None なら全員が認可済み
    fail_next: bool = False
    transfers: list[dict] = field(default_factory=list)
    # transfer_id → 状況（既定は承認待ち）。テストが「銀行で承認した」「期限が切れた」を作る
    statuses: dict[str, str] = field(default_factory=dict)
    # 本人の出金明細（user_id → エントリ）
    outgoing_entries: dict[str, list[OutgoingEntry]] = field(default_factory=dict)
    poll_error: bool = False

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

    def get_transfer(self, transfer_id: str) -> TransferInfo:
        if self.poll_error:
            raise BankAdapterError("bank_adapter_502")
        return TransferInfo(
            transfer_id=transfer_id,
            status=self.statuses.get(transfer_id, "awaiting_approval"),
            approval_expires_at=None,
        )

    def outgoing(self, user_id: str, date_from: date, date_to: date) -> list[OutgoingEntry]:
        return [e for e in self.outgoing_entries.get(user_id, []) if date_from <= e.date <= date_to]
