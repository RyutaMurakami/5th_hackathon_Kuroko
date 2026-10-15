"""シナリオの進行ヒント（SPEC 7.5）。イベントの状態から導く固定の文。LLM は使わない。

「いまの段階で、次に何を、どこで、誰がするか」と、入力の候補（架空の値）を返す。案内だけで、
操作の代行や承認の近道ではない。画面は2つある（SPEC 7.7）:
- 体験用（審査員）: 参加者・承認者の操作を、Web の2人の列のカードで行う
- 実演用（開発者）: 参加者・承認者は、Slack と本物の銀行（sunabar）で操作する
"""

from typing import Any

from src.models.event import Event, EventStatus, Participant, ParticipantRole
from src.seed.sample_company import demo_participants

TOTAL = 9

# デモの開催日は 10月30日（金）19時。場所は聞かない（参加者の開催希望駅から、コードが探す）
FIRST_REQUEST = "10月30日の19時から、第一開発チーム10人の歓送迎会を行いたい"


def plan_example() -> dict[str, Any]:
    """計画のカードに、はじめから入れておく値（架空）。主役は、名簿から選べる人を返す。

    名簿の主役は外せない（`locked`）。幹事・デモの登場人物（承認者を含む）は、主役にできない。
    """
    honorees = [
        {
            "user_id": p.user_id,
            "display_name": p.display_name,
            "selected": p.role is ParticipantRole.GUEST_OF_HONOR,
            "locked": p.role is ParticipantRole.GUEST_OF_HONOR,
        }
        for p in demo_participants()
        if p.role in (ParticipantRole.PARTICIPANT, ParticipantRole.GUEST_OF_HONOR)
        and not p.demo_persona
    ]
    return {
        "title": "第一開発チーム 歓送迎会", "datetime": "2026-10-30T19:00", "party_size": 10,
        "budget_per_person_yen": 5000, "rsvp_deadline": "2026-10-23", "honorees": honorees,
        "station": "新宿",
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
        "あなたが幹事です。下の入力の候補を押して送ると、KUROKO が、確認したい項目を"
        "カードで出します。" + tail,
        {"plan": plan_example()}, [FIRST_REQUEST],
    )  # fmt: skip


def _hint_for(
    event: Event, people: list[Participant], *, has_receipt: bool, retro_ready: bool = False,
    split_ready: bool = False, approved: bool = False,
) -> dict[str, Any]:  # fmt: skip
    s = event.status
    # 体験用でないイベント（本番の幹事）も、参加者は Slack と銀行で操作する
    live = event.ui_mode == "live" or not event.sandbox
    # 振込を、本物の銀行（sunabar。資金は仮想）で承認するか。審査員の体験も、既定でそうする
    real_bank = live or event.bank_approval == "bank"
    # 参加者・承認者が操作する場所の言い方
    cards = "Slack の DM" if live else "右の2人の列のカード（Slack の DM でも同じ）"
    where = "slack" if live else "web"
    if s is EventStatus.PLANNING:
        return _hint(
            1, "web", "幹事", "計画を確かめて、確定する",
            "KUROKO が出した計画のカードで、題名・日時・人数・予算・主役・出欠の回答期限を"
            "確かめて「この内容で進める」を押します。確定すると、参加者に出欠と委任の依頼が"
            "届きます。お店の場所は、参加者の開催希望駅から KUROKO が探すので、入れません。",
            {"plan": plan_example()}, [ASK_POLICY],
        )  # fmt: skip
    if s is EventStatus.RSVP:
        pending = [p.display_name or p.user_id for p in people if p.rsvp_status.value == "pending"]
        return _hint(
            2, where, "参加者", "出欠と委任に答える",
            "赤坂 くらお・赤くら 花子の2人に、出欠と委任（上限つき）の依頼が届きました。"
            f"{cards}で、開催希望駅と苦手な食べ物を確かめて「参加して、委任に同意する」を"
            "押します。ほかの参加者のぶんは、デモ用の代行が済ませます。2人が答えると、"
            "KUROKO がみなさんの開催希望駅から、お店を探し始めます。",
            {"waiting": pending}, [ASK_POLICY],
        )  # fmt: skip
    if s is EventStatus.VENUE:
        chosen = bool((event.venue or {}).get("place_id"))
        return _hint(
            3, "web", "幹事", "予約の画面を送り、内容を確定する" if chosen else "店を選ぶ",
            (
                "お店に予約したあと、予約完了の画面を、チャットに画像で送ります（「サンプルの"
                "予約画面を送る」で試せます）。KUROKO が読み取った内容を確かめて確定すると、"
                "参加者に開催の案内が届きます。コース単価が規程の上限を超えると、予算超過の"
                "確認に進みます。"
                if chosen
                else "KUROKO が、みなさんの開催希望駅からの帰りやすさ・苦手な食べ物・"
                "過去の実績から、お店の候補を出します（30秒ほど）。"
                "候補は Google マップで確かめられます。"
                "「この店にする」で選びます。"
            ),
            {"reservation": {"venue_name": "デモ用居酒屋", "party_size": 10,
                             "datetime": event.datetime.isoformat(), "course_price_yen": 4950}},
            [ASK_BUDGET],
        )  # fmt: skip
    if s is EventStatus.BOOKED:
        return _hint(
            4, "web", "幹事", "開催後に「開催が終わった」を押す",
            "予約が確定し、参加者に開催の案内が届きました。開催が終わったら、チャットの中の"
            "「開催が終わった」を押すと、領収書の送信に進みます。",
            None, [ASK_APPROVER],
        )  # fmt: skip
    if s in (EventStatus.DAY_OF, EventStatus.RECEIPT):
        return _hint(
            5, "web", "幹事", "領収書の金額を確定する",
            "領収書の写真を、チャットに画像で送ります（「サンプルの領収書を送る」で試せます）。"
            "KUROKO が読み取った金額を確かめて確定します（読み取りに失敗したときだけ、"
            "手入力できます）。確定すると、規程にもとづいて、決まった手順のコードが按分を計算します。",
            {"receipt": {"total_amount_yen": 49500}, "confirmed": has_receipt}, [ASK_POLICY],
        )  # fmt: skip
    if s is EventStatus.SPLIT and not split_ready:
        return _hint(
            5, "system", "KUROKO", "按分を計算する",
            "KUROKO が、会社の規程と按分ルールを確認して、按分を計算しています。",
        )  # fmt: skip
    if s is EventStatus.SPLIT:
        return _hint(
            6, "web", "幹事", "按分の内訳を確かめて、承認者に承認を依頼する",
            "チャットの中の按分の内訳（負担の係数・会社の補助・端数）を確かめて、「承認者に承認を"
            "依頼する」を押します。押すと、承認者（赤くら 花子）に承認の依頼が届きます。",
            None, [ASK_APPROVER],
        )  # fmt: skip
    if s is EventStatus.APPROVAL and approved:
        return _hint(
            7, "web", "幹事", "振込の依頼を送ることを承認する",
            "承認者が按分を承認しました。チャットの中の「振込の依頼を送る」を押すと、参加者に、"
            "銀行で承認するお願いが届きます（お金が動くのは、各自が銀行で承認したときです）。",
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
        if real_bank:
            do = (
                "赤坂 くらお・赤くら 花子の2人の振込の承認が、銀行（sunabar。資金は仮想）で"
                "求められています。それぞれの口座（くらお＝口座 No.2、花子＝口座 No.3。"
                "提出文書のログイン情報）で sunabar のサービスサイトに入り、"
                "「お知らせ」から、10分以内に承認します。"
            )
        else:
            do = (
                "赤坂 くらお・赤くら 花子の2人に、振込の承認の依頼が届きました。2人の列の"
                "「銀行で承認する（体験用）」を押すと、銀行の承認ページを模した画面が開くので、"
                "「承認する」を押します。"
            )
        return _hint(
            7, "bank" if real_bank else "web", "参加者", "銀行で振込を承認する",
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
            "出席者の全員に、満足度（1〜5）を聞くカードを送りました。赤坂 くらお・赤くら 花子の"
            f"2人は、{cards}で答えます。2人が答えると、幹事の確認に進みます"
            "（待たずに進めたいときは、幹事が「回答を締め切る」を押せます）。",
        )  # fmt: skip
    if s is EventStatus.RETRO:
        return _hint(
            9, "web", "幹事", "振り返りを確認し、次回に覚えさせる",
            "チャットの中の振り返りのカードで、実績と満足度の集計を見て、「次回もこの店を"
            "使いたいか」に答え、「次回に覚えさせる」を押します。保存されるのは、定型の事実だけです。",
        )  # fmt: skip
    return _hint(
        9, "system", "KUROKO", "デモは、ここまでです",
        "依頼から、出欠・店選び・予約・按分・承認・振込・振り返りまで、すべて終わりました。"
        "覚えさせた内容は、次の企画の店の候補に使われます。「新しく依頼する」から、"
        "もう一度試せます。",
    )  # fmt: skip


# 実演用（SPEC 7.8）: 幹事の操作は、Web ではなく Slack の DM で行う。画面は進み具合を映す
_LIVE_DO = {
    "planning": "Slack の DM に、計画の案のカードが届きます。内容を確かめて「この内容で進める」を"
    "押します（Slack で依頼を送ったときは、読み取った案が出ています）。",
    "venue_choose": "Slack の DM に、お店の候補が届きます（30秒ほど）。Google マップで確かめて、"
    "「この店にする」のボタンで選びます。",
    "venue_reserved": "お店に予約したあと、予約完了の画面を、Slack の DM に画像で送ります。"
    "読み取った内容を確かめて「この内容で確定する」を押すと、参加者に開催の案内が届きます。",
    "booked": "予約が確定しました。開催が終わったら、Slack の DM の「開催が終わった」を押します。",
    "receipt": "領収書の写真を、Slack の DM に画像で送ります。読み取った金額を確かめて"
    "「この内容で確定する」を押すと、規程にもとづいて按分を計算します。",
    "split": "Slack の DM に、按分の内訳が届きます。確かめて「承認者に承認を依頼する」を押します。",
    "transfers": "承認者が按分を承認しました。Slack の DM の「振込の依頼を送る」を押すと、"
    "参加者に、銀行で承認するお願いが届きます。",
    "retro": "Slack の DM に、振り返りのまとめが届きます。「記憶に残す」かを選びます。",
}


def hint_for(
    event: Event, people: list[Participant], *, has_receipt: bool, retro_ready: bool = False,
    split_ready: bool = False, approved: bool = False,
) -> dict[str, Any]:  # fmt: skip
    """進行ヒント。実演用のイベントでは、幹事の操作を Slack の DM に案内する（SPEC 7.8）。"""
    hint = _hint_for(
        event, people, has_receipt=has_receipt, retro_ready=retro_ready,
        split_ready=split_ready, approved=approved,
    )  # fmt: skip
    if event.ui_mode != "live" or hint.get("who") != "幹事":
        return hint
    s = event.status
    chosen = bool((event.venue or {}).get("place_id"))
    key = {
        EventStatus.PLANNING: "planning",
        EventStatus.VENUE: "venue_reserved" if chosen else "venue_choose",
        EventStatus.BOOKED: "booked",
        EventStatus.DAY_OF: "receipt",
        EventStatus.RECEIPT: "receipt",
        EventStatus.SPLIT: "split",
        EventStatus.APPROVAL: "transfers",
        EventStatus.RETRO: "retro",
    }.get(s)
    if key is None:
        return hint
    return {**hint, "where": "slack", "do": _LIVE_DO[key]}
