"""参加者への Slack DM の通知（支払いの開始・作り直し・完了・失敗。SPEC 7.2・8.5）。

文面は**固定のテンプレート**で、金額・期限などの値はコードが入れる（LLM は使わない）。口座番号・
トークンは載せない。通知の失敗は支払いの状態を変えない（呼び出し側が握りつぶしてログに残す）。
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


def yen(amount: int) -> str:
    return f"{amount:,}円"


class Notifier(Protocol):
    def transfer_requested(self, payment: dict[str, Any], *, reissued: bool) -> None: ...

    def completed(self, payment: dict[str, Any]) -> None: ...

    def failed(self, payment: dict[str, Any]) -> None: ...


@dataclass
class NullNotifier:
    """ローカル・テスト用。送らずに記録する。"""

    sent: list[tuple[str, str, str]] = field(default_factory=list)  # (種類, 支払いID, 本文)

    def transfer_requested(self, payment, *, reissued):
        self.sent.append(("reissued" if reissued else "requested", payment["payment_id"], ""))

    def completed(self, payment):
        self.sent.append(("completed", payment["payment_id"], ""))

    def failed(self, payment):
        self.sent.append(("failed", payment["payment_id"], ""))


def requested_text(title: str, amount_yen: int, *, reissued: bool) -> str:
    lead = "承認の期限が切れたため、振込の依頼を作り直しました。" if reissued else ""
    return (
        f"{lead}「{title}」の負担額 {yen(amount_yen)} の振込を、あなたの委任の範囲内で"
        "依頼しました。\n"
        "*10分以内に*、sunabar サービスサイトの「お知らせ」から振込の承認ページを開いて、"
        "取引パスワードで承認してください。承認すると、実際に振込が行われます。"
    )


def completed_text(title: str, amount_yen: int) -> str:
    return (
        f"「{title}」の負担額 {yen(amount_yen)} の入金を確認しました。"
        "お支払いありがとうございました。"
    )


def failed_text(title: str, amount_yen: int) -> str:
    return (
        f"「{title}」の負担額 {yen(amount_yen)} の支払いを完了できませんでした。"
        "幹事に報告しました。お手数ですが、幹事と直接ご相談ください。"
    )


class SlackNotifier:
    """Slack の DM に送る。宛先は Firestore の参加者の `slack_user_id`（kuroko-api が書く）。"""

    def __init__(self, *, token: str, db: Any) -> None:
        from slack_sdk import WebClient

        self._slack = WebClient(token=token)
        self._db = db

    def _lookup(self, payment: dict[str, Any]) -> tuple[str | None, str]:
        event = self._db.collection("events").document(payment["event_id"])
        title = (event.get().to_dict() or {}).get("title") or "飲み会"
        snap = event.collection("participants").document(payment["payer_user_id"]).get()
        return (snap.to_dict() or {}).get("slack_user_id"), title

    def _send(self, payment: dict[str, Any], build) -> None:
        slack_id, title = self._lookup(payment)
        if not slack_id:
            logger.warning("no slack user for payer: payment=%s", payment["payment_id"])
            return
        self._slack.chat_postMessage(channel=slack_id, text=build(title))

    def transfer_requested(self, payment, *, reissued):
        self._send(payment, lambda t: requested_text(t, payment["amount_yen"], reissued=reissued))

    def completed(self, payment):
        self._send(payment, lambda t: completed_text(t, payment["amount_yen"]))

    def failed(self, payment):
        self._send(payment, lambda t: failed_text(t, payment["amount_yen"]))
