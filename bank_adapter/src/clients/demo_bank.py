"""デモ用の銀行: 指定した振込元だけを実機（sunabar）に通し、残りの振込は代行する（SPEC 8.10）。

デモでは、全員ぶんの振込を銀行のサービスサイトで1件ずつ承認するのは現実的でない。そこで、
**実際に銀行で承認する人（`live_payer_labels`）だけ**を実機に通し、ほかの人の振込は、ここで
「承認済み」として記録する（銀行は呼ばない）。BankClient の形は実機と同じなので、上流
（委任状の検証・Policy Gate・明細での入金の確認）は、全員ぶんが同じコードで動く。

代行した振込は、受付番号が `SIM` で始まり、記録に `simulated` が付く。実機の明細には載らない。
"""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.clients.bank import BankClient, BankError, BankTransaction
from src.db.store import Store

SIM_PREFIX = "SIM"
JST = ZoneInfo("Asia/Tokyo")


class DemoBank:
    def __init__(
        self,
        *,
        real: BankClient,
        store: Store,
        live_payer_labels: frozenset[str],
        today: Callable[[], date] | None = None,
    ) -> None:
        self._real, self._store, self._live = real, store, live_payer_labels
        self._today = today or (lambda: datetime.now(JST).date())

    def is_simulated(self, payer_label: str) -> bool:
        return payer_label not in self._live

    # --- BankClient ---
    def has_account(self, *, label: str) -> bool:
        # 代行する人は、銀行の口座（トークン）を使わない
        return True if self.is_simulated(label) else self._real.has_account(label=label)

    def holder_name(self, *, label: str) -> str:
        try:
            name = self._real.holder_name(label=label)
        except BankError:
            name = ""
        return name or f"ﾃﾞﾓ {label}"  # 実機の口座が無い人の、代行の明細だけで使う名義

    def create_transfer(
        self,
        *,
        payer_label: str,
        payee_label: str,
        amount_yen: int,
        request_key: str,
        idempotency_key: str,
    ) -> str:
        if not self.is_simulated(payer_label):
            return self._real.create_transfer(
                payer_label=payer_label,
                payee_label=payee_label,
                amount_yen=amount_yen,
                request_key=request_key,
                idempotency_key=idempotency_key,
            )
        apply_no = f"{SIM_PREFIX}{request_key}"  # 依頼ごとに決まるので、再送しても1件
        self._store.save_simulated(
            apply_no,
            {
                "payer_label": payer_label,
                "payee_label": payee_label,
                "amount_yen": amount_yen,
                "date": self._today().isoformat(),
            },
        )
        return apply_no

    def create_held(
        self, *, payer_label: str, payee_label: str, amount_yen: int, request_key: str
    ) -> str:
        """体験用（SPEC 7.7）: 「承認待ち」の代行の振込。`approve` されるまで、明細に載らない。"""
        apply_no = f"{SIM_PREFIX}{request_key}"
        if apply_no not in self._store.list_simulated():  # 再送で、承認済みを未承認に戻さない
            self._store.save_simulated(
                apply_no,
                {
                    "payer_label": payer_label,
                    "payee_label": payee_label,
                    "amount_yen": amount_yen,
                    "date": self._today().isoformat(),
                    "approved": False,
                },
            )
        return apply_no

    def approve(self, apply_no: str) -> bool:
        """体験用の「銀行で承認する」。承認待ちの代行の振込だけ（本物の振込には効かない）。"""
        rec = self._store.list_simulated().get(apply_no)
        if rec is None or rec.get("approved", True):
            return False
        self._store.save_simulated(
            apply_no, rec | {"approved": True, "date": self._today().isoformat()}
        )
        return True

    def is_processed(self, *, payer_label: str, apply_no: str) -> bool:
        if not apply_no.startswith(SIM_PREFIX):
            return self._real.is_processed(payer_label=payer_label, apply_no=apply_no)
        rec = self._store.list_simulated().get(apply_no)
        return bool(rec and rec["payer_label"] == payer_label and rec.get("approved", True))

    def transactions(
        self, *, label: str, date_from: date, date_to: date
    ) -> tuple[list[BankTransaction], bool]:
        rows: list[BankTransaction] = []
        has_next = False
        if self._real.has_account(label=label):
            rows, has_next = self._real.transactions(
                label=label, date_from=date_from, date_to=date_to
            )
        for apply_no, rec in sorted(self._store.list_simulated().items()):
            day = date.fromisoformat(rec["date"])
            if not date_from <= day <= date_to or not rec.get("approved", True):
                continue  # 承認待ち（体験用）の振込は、まだ成立していない
            # 摘要は実機と同じ形（「振込 ＋ 相手の名義」）
            if rec["payer_label"] == label:
                other, direction = rec["payee_label"], "out"
            elif rec["payee_label"] == label:
                other, direction = rec["payer_label"], "in"
            else:
                continue
            rows.append(
                BankTransaction(
                    f"{apply_no}-{direction}",
                    day,
                    direction,
                    rec["amount_yen"],
                    f"振込 {self.holder_name(label=other)}",
                )
            )
        return rows, has_next
