"""シナリオの進行ヒント（SPEC 7.5。検証・デモ用）。イベントの状態から導く固定の文。LLM は使わない。

「いまの段階で、次に何を、どこで、誰がするか」と入力例（架空の値）を返す。案内だけで、操作の代行や
承認の近道ではない（Slack・銀行で人が行う操作は、そこで行うことを示すだけ）。
"""

from typing import Any

from src.models.event import Event, EventStatus, Participant

TOTAL = 9


def _hint(step: int, where: str, who: str, title: str, do: str, example: Any = None) -> dict:
    return {
        "step": step, "total": TOTAL, "where": where, "who": who, "title": title,
        "do": do, "example": example,
    }  # fmt: skip


def hint_for(event: Event, people: list[Participant], *, has_receipt: bool) -> dict[str, Any]:
    s = event.status
    if s is EventStatus.PLANNING:
        return _hint(
            1, "web", "幹事", "KUROKO に依頼して、計画を確定する",
            "チャットで依頼し、条件（日時・人数・エリア・予算）を整えたら「計画を確定」を"
            "押します。確定すると、参加者に Slack で出欠依頼が届きます。",
            {"chat": "来週金曜の19時、チーム8人で渋谷で軽く飲みたい。予算は1人5,000円くらい。",
             "plan": {"title": "チーム飲み会", "area": "渋谷", "party_size": 8,
                      "budget_per_person_yen": 5000}},
        )  # fmt: skip
    if s is EventStatus.RSVP:
        pending = [p.display_name or p.user_id for p in people if p.rsvp_status.value == "pending"]
        return _hint(
            2,
            "slack",
            "参加者",
            "出欠と委任を Slack で回答する",
            "参加者が Slack の DM のボタンで出欠に答え、出席の人は送金の委任（上限つき）に"
            "同意します。全員が回答すると、店の候補に進みます。",
            {"waiting": pending},
        )
    if s is EventStatus.VENUE:
        return _hint(
            3,
            "web",
            "幹事",
            "店の候補から選ぶ",
            "チャットで「お店を探して」と頼むと、帰りやすさと希望から候補が出ます。"
            "選んだら「この店にする」を押します。",
            {"chat": "お店を探して"},
        )
    if s is EventStatus.BOOKED:
        return _hint(
            4, "web", "幹事", "予約の内容を確定する",
            "店で予約したら、予約画面をアップロードするか、手入力で内容を確定します。",
            {"reservation": {"venue_name": "炭火酒場 渋谷店", "party_size": 8,
                             "datetime": "2026-10-23T19:00:00+09:00", "course_price_yen": 4500}},
        )  # fmt: skip
    if s in (EventStatus.DAY_OF, EventStatus.RECEIPT):
        return _hint(
            5,
            "web",
            "幹事",
            "領収書の金額を確定する",
            "開催後、領収書をアップロードして金額を確かめます（読み取りに失敗したときだけ"
            "手入力できます）。確定すると按分の計算に進みます。",
            {"receipt": {"total_amount_yen": 48000}, "confirmed": has_receipt},
        )
    if s in (EventStatus.SPLIT, EventStatus.APPROVAL):
        approvers = [p.display_name or p.user_id for p in people if p.role.value == "approver"]
        return _hint(
            6,
            "slack",
            "承認者",
            "按分を Slack で承認する",
            "承認者に、按分の内訳つきの承認依頼が Slack で届きます。"
            "承認者が承認すると請求に進みます。",
            {"approvers": approvers},
        )
    if s is EventStatus.PAYMENT:
        return _hint(
            7,
            "bank",
            "参加者",
            "銀行（sunabar）で振込を承認する",
            "参加者ごとに振込の承認が必要です。sunabar のサービスサイトで承認してください。"
            "承認されると、入金の確認に進みます。",
        )
    if s is EventStatus.COMPLETED:
        return _hint(
            8,
            "system",
            "KUROKO",
            "入金の確認と経費記録",
            "全員の入金を明細で確認し、経費精算の記録を作ります。完了すると振り返りが始まります。",
        )
    return _hint(
        9,
        "slack",
        "参加者",
        "振り返りに答える",
        "参加者が Slack の DM で満足度（1〜5）を答えます。"
        "集まったら、次回に覚えさせる内容を Web で確認します。",
    )
