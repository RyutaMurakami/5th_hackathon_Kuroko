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
            "あなたが幹事です。チャットで依頼し、条件（日時・人数・エリア・予算）を整えたら"
            "「計画を確定」を押します。確定すると、参加者に Slack で出欠依頼が届きます。"
            "開催日は今日にしてください（入金の確認が、開催日からの明細を見るため）。",
            {"chat": "今日の19時から、チーム10人の歓送迎会を渋谷でやりたい。予算は1人5,000円くらい",
             "plan": {"title": "営業1課 歓送迎会", "area": "渋谷", "party_size": 10,
                      "budget_per_person_yen": 5000}},
        )  # fmt: skip
    if s is EventStatus.RSVP:
        pending = [p.display_name or p.user_id for p in people if p.rsvp_status.value == "pending"]
        return _hint(
            2,
            "slack",
            "参加者",
            "出欠と委任を Slack で回答する",
            "赤坂 くらお・赤くら 花子の2人に、出欠と委任（上限つき）の依頼が届きます。"
            "右の2人の列のカード（または Slack の DM）で「参加して、委任に同意する」を押します。"
            "ほかの参加者のぶんは、デモ用の代行が済ませます。2人が回答すると、店の候補に進みます。",
            {"waiting": pending},
        )
    if s is EventStatus.VENUE:
        return _hint(
            3, "web", "幹事", "店を選び、予約の内容を確定する",
            "チャットで「お店を探して」と頼むと、帰りやすさと希望から候補が出ます。選んだら「この店にする」を押し、"
            "店で予約したあと、予約の内容を確定します。コース単価が規程の上限を超えると、"
            "予算超過の確認（幹事 → 承認者）に進みます。",
            {"chat": "お店を探して",
             "reservation": {"venue_name": "炭火酒場 渋谷店", "party_size": 10,
                             "datetime": event.datetime.isoformat(), "course_price_yen": 4500}},
        )  # fmt: skip
    if s is EventStatus.BOOKED:
        return _hint(
            4,
            "web",
            "幹事",
            "開催後に「開催が終わった」を押す",
            "予約が確定しました。開催が終わったら「開催が終わった」を押すと、領収書のアップロードに進みます。",
        )
    if s in (EventStatus.DAY_OF, EventStatus.RECEIPT):
        return _hint(
            5,
            "web",
            "幹事",
            "領収書の金額を確定する",
            "領収書をアップロードして、読み取った金額を確かめます（読み取りに失敗したときだけ"
            "手入力できます）。確定すると按分の計算に進みます。",
            {"receipt": {"total_amount_yen": 49500}, "confirmed": has_receipt},
        )
    if s in (EventStatus.SPLIT, EventStatus.APPROVAL):
        return _hint(
            6,
            "slack",
            "承認者",
            "按分を Slack で承認する",
            "承認者（規程で決まる。部長の赤くら 花子）に、按分の内訳つきの承認依頼が届きます。"
            "花子の列のカード（または Slack の DM）で承認すると、請求に進みます。",
        )
    if s is EventStatus.PAYMENT:
        return _hint(
            7,
            "bank",
            "参加者",
            "銀行（sunabar）で振込を承認する",
            "赤坂 くらお・赤くら 花子の2人に、振込の承認の依頼が届きます。2人の列のカードの"
            "「銀行で承認する（体験用）」を押してください（実演用のイベントでは、それぞれの口座で "
            "sunabar のサービスサイトに入り、10分以内に承認します）。ほかの人の振込は代行され、"
            "全員ぶんの入金を確認できると、1〜2分で自動で完了になります。",
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
