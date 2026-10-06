"""銀行クライアントのインターフェース（スタブと sunabar の実装が同じ形）。

口座番号・アクセストークンは、このインターフェースの内側（clients/）だけで扱い、
services/ と routers/ には出さない。
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol


class BankError(Exception):
    """銀行が依頼を受け付けなかった、または通信に失敗した。message に秘密を入れない。"""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


@dataclass(frozen=True)
class BankTransaction:
    item_key: str
    date: date
    direction: Literal["in", "out"]
    amount_yen: int
    remarks: str


class BankClient(Protocol):
    def create_transfer(
        self,
        *,
        payer_label: str,
        payee_label: str,
        amount_yen: int,
        request_key: str,
        idempotency_key: str,
    ) -> str:
        """振込を依頼して、受付番号（apply_no）を返す。この時点では送金は成立していない。"""

    def is_processed(self, *, payer_label: str, apply_no: str) -> bool:
        """銀行が「手続済」にしたか。承認前・期限切れは False（銀行は 0件で返す）。"""

    def transactions(
        self, *, label: str, date_from: date, date_to: date
    ) -> tuple[list[BankTransaction], bool]:
        """入出金明細と、続きがあるか。"""

    def has_account(self, *, label: str) -> bool:
        """このラベルの口座を使えるか（トークンがあり、口座が引けるか）。"""
