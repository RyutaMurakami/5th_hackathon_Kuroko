"""シナリオの進行ヒント（SPEC 7.5）。イベントの状態から導く固定の文。LLM は使わない。

「いまの段階で、次に何を、どこで、誰がするか」と、入力の候補（架空の値）を返す。案内だけで、
操作の代行や承認の近道ではない。画面は2つある（SPEC 7.7）:
- 体験用（審査員）: 参加者・承認者の操作を、Web の2人の列のカードで行う
- 実演用（開発者）: 参加者・承認者は、Slack と本物の銀行（sunabar）で操作する
"""

from typing import Any

from src.models.event import Event, EventStatus, Participant

TOTAL = 9

FIRST_REQUEST = (
    "今日の19時から、第一開発チーム10人の歓送迎会を渋谷でやりたい。予算は1人5,000円くらい"
)
PLAN = {
    "title": "第一開発チーム 歓送迎会", "area": "渋谷", "party_size": 10,
    "budget_per_person_yen": 5000,
}  # fmt: skip
# 規程のことを聞くと、エージェントが規程の文書を調べて、条を添えて答える（`retrieve_policy`）
ASK_POLICY = "部長と新人の負担はどう違いますか？規程を確認してください"
ASK_BUDGET = "コース料金の上限は、規程ではいくらですか？"
ASK_APPROVER = "按分は、だれが承認することになっていますか？"


def _hint(
    step: int, where: str, who: str, title: str, do: str, example: dict | None = None,
    chats: list[str] | None = None,
) -> dict:  # fmt: skip
    example = dict(example or {})
    if chats:
        example["chat"], example["chats"] = chats[0], chats  # チャットの入力の候補
    return {
        "step": step, "total": TOTAL, "where": where, "who": who, "title": title,
        "do": do, "example": example or None,
    }  # fmt: skip


def start_hint(*, live: bool) -> dict[str, Any]:
    """イベントを作る前（最初の依頼を送る前）のヒント。"""
    tail = (
        "参加者の2人は Slack で、振込は本物の銀行（sunabar）で操作します。"
        if live
        else "参加者の2人の操作は、右の2列のカードで、あなたが代わりに行えます。"
    )
    return _hint(
        1, "web", "幹事", "KUROKO に依頼する",
        "あなたが幹事です。下の入力の候補を押して送ると、KUROKO が依頼を整理します。" + tail,
        {"plan": PLAN}, [FIRST_REQUEST],
    )  # fmt: skip


def hint_for(
    event: Event, people: list[Participant], *, has_receipt: bool, retro_ready: bool = False
) -> dict[str, Any]:
    s = event.status
    # 体験用でないイベント（本番の幹事）も、参加者は Slack と銀行で操作する
    live = event.ui_mode == "live" or not event.sandbox
    # 参加者・承認者が操作する場所の言い方
    cards = "Slack の DM" if live else "右の2人の列のカード（Slack の DM でも同じ）"
    where = "slack" if live else "web"
    if s is EventStatus.PLANNING:
        return _hint(
            1, "web", "幹事", "計画を確かめて、確定する",
            "チャットの中の「計画を確定する」のカードで、題名・日時・エリア・人数・予算を確かめて"
            "「この内容で進める」を押します。確定すると、参加者に出欠と委任の依頼が届きます。"
            "開催日は今日にしてください（入金の確認が、開催日からの明細を見るため）。",
            {"plan": PLAN}, [FIRST_REQUEST, ASK_POLICY],
        )  # fmt: skip
    if s is EventStatus.RSVP:
        pending = [p.display_name or p.user_id for p in people if p.rsvp_status.value == "pending"]
        return _hint(
            2, where, "参加者", "出欠と委任に答える",
            "赤坂 くらお・赤くら 花子の2人に、出欠と委任（上限つき）の依頼が届きました。"
            f"{cards}で「参加して、委任に同意する」を押します。ほかの参加者のぶんは、"
            "デモ用の代行が済ませます。2人が答えると、店の候補に進みます。",
            {"waiting": pending}, [ASK_POLICY],
        )  # fmt: skip
    if s is EventStatus.VENUE:
        return _hint(
            3, "web", "幹事", "店を選び、予約の内容を確定する",
            "チャットの中の「店の候補を出す」を押すと、全員の帰りやすさと希望から候補が出ます"
            "（チャットで「お店を探して」と頼んでも同じ）。店を選び、店で予約したあと、"
            "予約画面（サンプルをダウンロードできます）をアップロードして、読み取った内容を"
            "確かめて確定します。コース単価が規程の上限を超えると、予算超過の確認に進みます。",
            {"reservation": {"venue_name": "炭火酒場 くろこ 渋谷店", "party_size": 10,
                             "datetime": event.datetime.isoformat(), "course_price_yen": 4950}},
            ["お店を探して", ASK_BUDGET],
        )  # fmt: skip
    if s is EventStatus.BOOKED:
        return _hint(
            4, "web", "幹事", "開催後に「開催が終わった」を押す",
            "予約が確定しました。開催が終わったら、チャットの中の「開催が終わった」を押すと、"
            "領収書のアップロードに進みます。",
            None, [ASK_APPROVER],
        )  # fmt: skip
    if s in (EventStatus.DAY_OF, EventStatus.RECEIPT):
        return _hint(
            5, "web", "幹事", "領収書の金額を確定する",
            "領収書（サンプルをダウンロードできます）をアップロードして、読み取った金額を確かめて"
            "確定します（読み取りに失敗したときだけ、手入力できます）。確定すると、"
            "決まった手順のコードが按分を計算します。",
            {"receipt": {"total_amount_yen": 49500}, "confirmed": has_receipt}, [ASK_POLICY],
        )  # fmt: skip
    if s in (EventStatus.SPLIT, EventStatus.APPROVAL):
        return _hint(
            6, where, "承認者", "按分を承認する",
            "承認者（規程で決まる。部長の赤くら 花子）に、按分の内訳つきの承認依頼が届きました。"
            + ("花子が Slack の DM で" if live else "花子の列のカード（Slack の DM でも同じ）で")
            + "「この按分を承認する」を押すと、請求に進みます。",
            None, [ASK_APPROVER],
        )  # fmt: skip
    if s is EventStatus.PAYMENT:
        if live:
            do = (
                "赤坂 くらお・赤くら 花子の2人に、Slack で振込の承認の依頼が届きました。"
                "それぞれの口座で sunabar のサービスサイトに入り、10分以内に承認します。"
            )
        else:
            do = (
                "赤坂 くらお・赤くら 花子の2人に、振込の承認の依頼が届きました。2人の列の"
                "「銀行で承認する（体験用）」を押すと、銀行の承認ページを模した画面が開くので、"
                "「承認する」を押します。"
            )
        return _hint(
            7, "bank" if live else "web", "参加者", "銀行で振込を承認する",
            do + "ほかの人の振込は代行され、全員ぶんの入金を確認できると、"
            "1〜2分で自動で完了になり、振り返りが始まります。",
        )  # fmt: skip
    if s is EventStatus.COMPLETED:
        return _hint(
            8, "system", "KUROKO", "入金の確認が済み、振り返りを始める",
            "全員の入金を明細で確認しました。まもなく、参加者に振り返り（満足度）の依頼が届きます。",
        )  # fmt: skip
    if s is EventStatus.RETRO and not retro_ready:
        return _hint(
            8, where, "参加者", "振り返りに答える",
            "赤坂 くらお・赤くら 花子の2人に、満足度（1〜5）を聞くカードが届きました。"
            f"{cards}で答えます。2人が答えると、幹事の確認に進みます"
            "（待たずに進めたいときは、幹事が「回答を締め切る」を押せます）。",
        )  # fmt: skip
    if s is EventStatus.RETRO:
        return _hint(
            9, "web", "幹事", "振り返りを確認し、次回に覚えさせる",
            "チャットの中の振り返りのカードで、実績と満足度の集計を見て、「次回もこの店を"
            "使いたいか」に答え、「次回に覚えさせる」を押します。保存されるのは、定型の事実だけです。",
        )  # fmt: skip
    return _hint(
        9, "system", "KUROKO", "完了",
        "この会は終わりました。覚えさせた内容は、次の企画の店の候補に使われます。"
        "「新しく依頼する」から、もう一度試せます。",
    )  # fmt: skip
