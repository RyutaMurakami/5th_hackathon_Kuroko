"""審査員の体験・撮影のために、sunabar の仮想口座の残高を確かめ、足りなければ補充の振込を依頼する。

資金は仮想。**振込の依頼を作るだけ**で、実際に動くのは、あなたが sunabar のサービスサイトで
振込元の口座（既定は acct03）にログインして、承認したとき。トークン・口座番号は表示しない。

使い方（`bank_adapter/` で。ADC に Secret Manager の読み取りが要る）:
  uv run python scripts/topup_demo_accounts.py                     # 残高を見るだけ
  uv run python scripts/topup_demo_accounts.py --apply             # 補充の振込を依頼
  uv run python scripts/topup_demo_accounts.py --apply --from acct03 --amount 60000 --to acct02

口座の役: acct01=幹事（受取）、acct02=くらお、acct03=花子（口座 No.1〜3）。
審査員の1回の通しで、くらおは 2,100円、花子は 4,800円 を振り込む（領収書 49,500円のとき）。
"""

import argparse
import uuid

from src.clients.sunabar import SunabarBank, secret_manager_tokens
from src.config import get_settings

PROJECT = "kuroko-509311"
ROLES = {"acct01": "幹事（受取）", "acct02": "くらお", "acct03": "花子"}
# 1回の通しで振り込む額（領収書 49,500円）
PER_RUN = {"acct02": 2_100, "acct03": 4_800}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="payer", default="acct03", help="振込元（既定: acct03）")
    ap.add_argument("--to", dest="payees", action="append", help="補充する口座（既定: 不足分）")
    ap.add_argument("--amount", type=int, default=60_000, help="1口座あたりの補充額（円）")
    ap.add_argument("--min-runs", type=int, default=20, help="最低、何回ぶん残っていてほしいか")
    ap.add_argument("--apply", action="store_true", help="補充の振込を依頼する（既定は見るだけ）")
    a = ap.parse_args()

    s = get_settings()
    bank = SunabarBank(
        base_url=s.sunabar_base_url,
        load_tokens=secret_manager_tokens(f"projects/{PROJECT}/secrets/sunabar-tokens"),
    )

    def balance(label: str) -> int:
        acct = bank._account(label)  # noqa: SLF001
        data = bank._request(  # noqa: SLF001
            label, "GET", "/accounts/balances", params={"accountId": acct["accountId"]}
        )
        return int((data.get("balances") or [{}])[0].get("balance") or 0)

    low = []
    for label, role in ROLES.items():
        bal = balance(label)
        per = PER_RUN.get(label)
        runs = f"（通し {bal // per} 回ぶん）" if per else ""
        need = per * a.min_runs if per else 0
        mark = "  ← 足りない" if per and bal < need else ""
        print(f"{label} {role}: {bal:,}円 {runs}{mark}")
        if per and bal < need:
            low.append(label)

    targets = a.payees or low
    if not targets:
        print("補充は要りません。")
        return
    payer_bal = balance(a.payer)
    for label in targets:
        if label == a.payer:
            continue
        if payer_bal < a.amount:
            print(f"{a.payer} の残高が足りません（{payer_bal:,}円）。")
            break
        if not a.apply:
            print(f"[dry-run] {a.payer} → {label} に {a.amount:,}円を依頼します（--apply で実行）")
            continue
        apply_no = bank.create_transfer(
            payer_label=a.payer, payee_label=label, amount_yen=a.amount,
            request_key=str(uuid.uuid4()), idempotency_key=str(uuid.uuid4()),
        )  # fmt: skip
        payer_bal -= a.amount
        print(f"依頼しました: {a.payer} → {label} {a.amount:,}円（受付番号 {apply_no}）")
    if a.apply:
        print(
            "\n次に、sunabar のサービスサイトに振込元の口座でログインし、「お知らせ」から、"
            "この振込を承認してください（約10分以内）。"
        )


if __name__ == "__main__":
    main()
