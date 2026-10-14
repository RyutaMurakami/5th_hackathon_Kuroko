"""Slack に送るカード（Block Kit）の組み立て。純粋な関数で、送信はしない。

- ボタンの値は `models.slack.encode_value`。Slack が署名するペイロードに入る（書き換えられない）
- 実名を見せるのは、幹事・承認者・本人への DM だけ（SPEC 10章）。LLM には渡さない
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from src.models.event import Event, Participant
from src.models.slack import Action, encode_value
from src.models.split import SplitResult

Blocks = list[dict[str, Any]]


def yen(amount: int) -> str:
    return f"{amount:,}円"


JST = timezone(timedelta(hours=9))


def _when(dt: datetime) -> str:
    """日時の表示（日本時間）。時差の無い値（ローカル・テスト）は、そのまま出す。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(JST)
    return f"{dt.month}/{dt.day} {dt:%H:%M}"


def maps_url(name: str, place_id: str = "") -> str:
    """Google マップでその店を開く URL（公開の検索 URL。API キーは要らない）。"""
    url = f"https://www.google.com/maps/search/?api=1&query={quote(name)}"
    # 幹事が名前で入れた店（候補に無い店）は、Google の place_id を持たない
    if place_id and not place_id.startswith("manual-"):
        url += f"&query_place_id={quote(place_id)}"
    return url


def _button(
    text: str, action: Action, value: dict[str, Any], style: str | None = None, mark: str = ""
) -> dict:
    # 同じ操作のボタンを並べるときは、`mark` で action_id を分ける（Slack は重複を認めない）
    button: dict[str, Any] = {
        "type": "button",
        "text": {"type": "plain_text", "text": text},
        "action_id": f"{action.value}:{mark}" if mark else action.value,
        "value": encode_value(value),
    }
    if style:
        button["style"] = style
    return button


def _input(block_id: str, label: str, placeholder: str) -> dict:
    """メッセージの入力欄（任意）。値は、ボタンを押したときの `state` で届く。"""
    return {
        "type": "input",
        "block_id": block_id,
        "optional": True,
        "label": {"type": "plain_text", "text": label},
        "element": {
            "type": "plain_text_input",
            "action_id": block_id,
            "placeholder": {"type": "plain_text", "text": placeholder},
        },
    }


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _organizer_label(organizer: Participant) -> str:
    """幹事の呼び方。デモの幹事は Web にログインした人で、名前を持たない（SPEC 7.6）。"""
    name = organizer.display_name
    return "幹事" if not name or name == "幹事" else f"幹事の {name} さん"


def consent_request(
    event: Event,
    participant: Participant,
    organizer: Participant,
    *,
    cap_yen: int,
    expires_at: datetime,
    slack_user_id: str,
) -> tuple[str, Blocks]:
    """出欠＋委任の依頼（SPEC 7.2）。同意の内容（上限・支払先・期限）を、そのまま見せる。"""
    title = event.title or "飲み会"
    text = f"「{title}」（{_when(event.datetime)}）への出欠と、支払いの委任のお願い"
    base = {"e": event.event_id, "u": participant.user_id, "s": slack_user_id}
    deadline = str(event.plan.get("rsvp_deadline") or "")  # 幹事が決めた回答期限（YYYY-MM-DD）
    due = f"\n回答期限: {int(deadline[5:7])}/{int(deadline[8:10])}" if len(deadline) == 10 else ""
    blocks: Blocks = [
        _section(f"*{title}*\n日時: {_when(event.datetime)}{due}"),
        _section(
            "*支払いの委任（同意の内容）*\n"
            f"• 上限: *{yen(cap_yen)}* まで\n"
            f"• 支払先: {_organizer_label(organizer)}だけ\n"
            f"• 期限: {expires_at:%Y/%m/%d} まで\n"
            "• 按分の承認のあと、あなたの支払いエージェントが、この範囲で振込を依頼します。"
            "実際の振込は、*銀行の承認ページで、あなたが承認したときだけ*実行されます。\n"
            "• 振込の依頼が作られる前なら、App Home からいつでも取り消せます。"
        ),
        # 最寄り駅・苦手な食べ物（任意）。「参加する」を押したときに、あわせて受け取る。
        # 駅は駅すぱあとで確かめ、食べ物は固定の語彙にして持つ（原文は保存しない。SPEC 7.5）
        _input("station", "最寄り駅", "例: 渋谷"),
        _input("dislikes", "苦手な食べ物・食べられないもの", "例: えびが苦手（無ければ空）"),
        {
            "type": "actions",
            "elements": [
                _button(
                    "参加して、委任に同意する",
                    Action.CONSENT,
                    base | {"k": "consent", "p": organizer.user_id, "c": cap_yen,
                            "x": expires_at.isoformat()},
                    "primary",
                ),
                _button("欠席する", Action.DECLINE, base | {"k": "decline"}),
            ],
        },
    ]  # fmt: skip
    return text, blocks


def split_approval_request(
    event: Event,
    split: SplitResult,
    people: dict[str, Participant],
    *,
    approver_slack_user_id: str,
) -> tuple[str, Blocks]:
    """按分の承認依頼（SPEC 7.1）。承認が請求・振込依頼のきっかけになることを明記する。"""
    title = event.title or "飲み会"
    payers = [r for r in split.rows if r.share_yen > 0 and r.user_id != event.organizer_user_id]
    lines = []
    for r in split.rows:
        name = people[r.user_id].display_name if r.user_id in people else r.user_id
        if r.weight == 0:
            lines.append(f"• {name}: 0円（主役）")
        else:
            lines.append(f"• {name}: {yen(r.share_yen)}（負担割合 {r.ratio_percent:.2f}%）")
    text = f"「{title}」の按分の承認をお願いします"
    blocks: Blocks = [
        _section(f"*{title}* の按分案（{_when(event.datetime)}）"),
        _section(
            f"会計 {yen(split.total_amount_yen)} − 会社補助 {yen(split.subsidy_yen)} = "
            f"*按分の対象額 {yen(split.base_amount_yen)}*\n"
            f"端数の不足分 {yen(split.shortfall_yen)} は、承認者（あなた）が負担します。"
        ),
        _section("\n".join(lines)),
        _section(
            f"*承認すると、{len(payers)}名の請求が作られ、各自の支払いエージェントが、委任の範囲内で"
            "幹事への振込を依頼します。各自が銀行で承認して、初めてお金が動きます。*\n"
            f"金額表の確認用ハッシュ: `{split.hash[:12]}`"
        ),
        {
            "type": "actions",
            "elements": [
                _button(
                    "この按分を承認する",
                    Action.APPROVE,
                    {"k": "approve", "e": event.event_id, "h": split.hash,
                     "s": approver_slack_user_id},  # fmt: skip
                    "primary",
                )
            ],
        },
    ]  # fmt: skip
    return text, blocks


def budget_request(
    event: Event, *, per_person_yen: int, limit_yen: int, approver_slack_user_id: str
) -> tuple[str, Blocks]:
    """予算超過の最終確認（SPEC 9.1。幹事の確認のあと、承認者に）。"""
    title = event.title or "飲み会"
    text = f"「{title}」が1人あたりの上限を超えています。確認をお願いします"
    blocks: Blocks = [
        _section(
            f"*{title}* の1人あたりの会計単価が *{yen(per_person_yen)}* で、"
            f"規程の上限 {yen(limit_yen)} を超えています。幹事は続行を確認済みです。"
        ),
        {
            "type": "actions",
            "elements": [
                _button(
                    "続行を承認する",
                    Action.BUDGET,
                    {"k": "budget", "e": event.event_id, "s": approver_slack_user_id},
                    "primary",
                )
            ],
        },
    ]
    return text, blocks


def feedback_request(
    event: Event, participant: Participant, *, slack_user_id: str, reminder: bool = False
) -> tuple[str, Blocks]:
    """振り返りの依頼（SPEC 7.4）。必須は満足度の1タップだけ。コメントは DM への返信で任意。"""
    title = event.title or "飲み会"
    lead = "（リマインドです）" if reminder else ""
    text = f"{lead}「{title}」はいかがでしたか"
    base = {"k": "rate", "e": event.event_id, "u": participant.user_id, "s": slack_user_id}
    blocks: Blocks = [
        _section(f"{lead}*{title}* はいかがでしたか？ 総合の満足度を、1タップで教えてください。"),
        {
            "type": "actions",
            "elements": [
                _button(f"{n}", Action.RATE, base | {"r": n}, None, mark=str(n))
                for n in range(1, 6)
            ],
        },
        _section(
            "1（残念）〜 5（とても良かった）。*個人ごとの回答・コメントは、幹事にも見えません。*"
            "集計だけが次回の店選びに使われ、コメントの原文は保存されません。"
        ),
    ]
    return text, blocks


def bank_request(
    event: Event, participant: Participant, *, amount_yen: int, slack_user_id: str
) -> tuple[str, Blocks]:
    """体験用の「銀行で承認してください」（SPEC 7.7）。本物の銀行のイベントでは使わない。"""
    title = event.title or "飲み会"
    text = f"「{title}」の負担額 {yen(amount_yen)} の振込を、銀行で承認してください"
    blocks: Blocks = [
        _section(
            f"「{title}」の負担額 *{yen(amount_yen)}* の振込を、"
            "あなたの委任の範囲内で依頼しました。\n"
            "銀行の承認ページで承認すると、実際に振込が行われます。"
        ),
        _section(
            "体験用: 本物では、銀行のサービスサイトにログインし、取引パスワードで承認します。"
            "ここでは、下のボタンがその代わりです（資金は仮想）。"
        ),
        {
            "type": "actions",
            "elements": [
                _button(
                    "銀行で承認する（体験用）",
                    Action.BANK,
                    {"k": "bank", "e": event.event_id, "u": participant.user_id,
                     "s": slack_user_id},  # fmt: skip
                    "primary",
                )
            ],
        },
    ]
    return text, blocks


def plan_request(event: Event, *, slack_user_id: str) -> tuple[str, Blocks]:
    """Slack で受けた依頼の、計画の案（SPEC 7.8）。幹事が確かめて「この内容で進める」を押す。

    細かい直し（主役・期限の変更など）は、Web の実演用の画面の計画のカードで行える。
    """
    draft = event.plan_draft
    when = datetime.fromisoformat(str(draft.get("datetime")))
    title = str(draft.get("title") or "飲み会")
    text = f"「{title}」の計画の案です。内容を確かめてください"
    lines = [
        "依頼を受け取りました。次の内容で進めてよいですか？",
        f"*題名*: {title}",
        f"*日時*: {_when(when)}",
        f"*人数*: {draft.get('party_size')}人",
        f"*1人あたりの予算*: {yen(int(draft.get('budget_per_person_yen') or 0))}",
        f"*出欠の回答期限*: {draft.get('rsvp_deadline') or '（なし）'}",
    ]
    value = {"k": "plan", "e": event.event_id, "s": slack_user_id}
    blocks: Blocks = [
        _section("\n".join(lines)),
        {
            "type": "actions",
            "elements": [_button("この内容で進める", Action.PLAN, value, "primary")],
        },
        _section(
            "お店の場所は、参加者の最寄り駅から KUROKO が探します。題名・日時・主役などを直す"
            "ときは、Web の実演用の画面の計画のカードで直せます。"
        ),
    ]
    return text, blocks


def event_notice(event: Event, *, guest_of_honor: bool = False) -> tuple[str, Blocks]:
    """開催の案内（予約が確定したあと。SPEC 7.5）。ボタンは無い。主役には、費用の話を書かない。"""
    title = event.title or "飲み会"
    venue = event.venue or {}
    name = str(venue.get("name") or venue.get("venue_name") or "")
    text = f"「{title}」の開催が決まりました（{_when(event.datetime)}・{name}）"
    lines = [f"*{title}* の開催が決まりました。", f"日時: {_when(event.datetime)}"]
    if name:
        url = maps_url(name, str(venue.get("place_id") or ""))
        lines.append(f"お店: {name}（<{url}|Google マップで見る>）")
    blocks: Blocks = [_section("\n".join(lines))]
    if not guest_of_honor:
        blocks.append(
            _section(
                "会費は、開催後に領収書の金額が確定してから、会社の規程にもとづいて按分し、"
                "承認者の承認のあとにご案内します。当日のお支払いは不要です。"
            )
        )
    return text, blocks


def resolved(text: str) -> Blocks:
    """ボタンを消して、結果だけを残す（押したあとのメッセージの置き換え）。"""
    return [_section(text)]


def home_view(
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """App Home。`items` は {title, lines, buttons}。ボタンは (text, action, value) の並び。"""
    blocks: Blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "KUROKO"}},
    ]
    if not items:
        blocks.append(_section("いま、あなたが関わっている飲み会はありません。"))
    for item in items:
        blocks.append({"type": "divider"})
        blocks.append(_section(f"*{item['title']}*\n" + "\n".join(item["lines"])))
        if item.get("buttons"):
            blocks.append(
                {
                    "type": "actions",
                    "elements": [_button(t, a, v, s) for t, a, v, s in item["buttons"]],
                }
            )
    return {"type": "home", "blocks": blocks}
