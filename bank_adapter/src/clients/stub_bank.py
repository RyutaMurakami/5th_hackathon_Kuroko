"""メモリ上の疑似銀行（ローカル・テスト用。TASKS B10）。sunabar と同じ BankClient の形。"""

from dataclasses import dataclass, field
from datetime import date

from src.clients.bank import BankError, BankTransaction


def _name(label: str) -> str:
    """スタブの口座名義。ラベルそのものは明細に出さない。"""
    return f"スタブ\u3000{abs(hash(label)) % 1000:03d}"


@dataclass
class _Pending:
    payer: str
    payee: str
    amount_yen: int
    approved: bool = False


@dataclass
class StubBank:
    labels: set[str] = field(default_factory=set)
    # True なら、依頼した時点で承認済みにする（ローカルの結合環境用）
    auto_approve: bool = False
    fail_next: str | None = None  # テスト用: 次の依頼を、この code で失敗させる
    pending: dict[str, _Pending] = field(default_factory=dict)
    ledger: dict[str, list[BankTransaction]] = field(default_factory=dict)
    create_calls: int = 0
    _seq: int = 0

    def has_account(self, *, label: str) -> bool:
        return not self.labels or label in self.labels

    def create_transfer(
        self,
        *,
        payer_label: str,
        payee_label: str,
        amount_yen: int,
        request_key: str,
        idempotency_key: str,
    ) -> str:
        self.create_calls += 1
        if self.fail_next:
            code, self.fail_next = self.fail_next, None
            raise BankError(code, "stub failure")
        self._seq += 1
        apply_no = f"STUB{self._seq:012d}"
        self.pending[apply_no] = _Pending(payer_label, payee_label, amount_yen)
        if self.auto_approve:
            self.approve(apply_no)
        return apply_no

    def approve(self, apply_no: str) -> None:
        """銀行の承認ページでの本人承認を模す（テストから呼ぶ）。"""
        p = self.pending[apply_no]
        if p.approved:
            return
        p.approved = True
        today = date.today()
        # 明細の摘要は「振込 ＋ 相手の名義」。名義は口座ごとに別（実機の挙動に合わせる）
        self.ledger.setdefault(p.payer, []).append(
            BankTransaction(f"{apply_no}-out", today, "out", p.amount_yen, f"振込 {_name(p.payee)}")
        )
        self.ledger.setdefault(p.payee, []).append(
            BankTransaction(f"{apply_no}-in", today, "in", p.amount_yen, f"振込 {_name(p.payer)}")
        )

    def is_processed(self, *, payer_label: str, apply_no: str) -> bool:
        p = self.pending.get(apply_no)
        return bool(p and p.payer == payer_label and p.approved)

    def transactions(
        self, *, label: str, date_from: date, date_to: date
    ) -> tuple[list[BankTransaction], bool]:
        rows = [t for t in self.ledger.get(label, []) if date_from <= t.date <= date_to]
        return rows, False
