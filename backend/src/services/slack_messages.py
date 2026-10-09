"""Slack に送るカード（Block Kit）の組み立て。純粋な関数で、送信はしない。

- ボタンの値は `models.slack.encode_value`。Slack が署名するペイロードに入る（書き換えられない）
- 実名を見せるのは、幹事・承認者・本人への DM だけ（SPEC 10章）。LLM には渡さない
"""

from datetime import datetime
from typing import Any

from src.models.event import Event, Participant
from src.models.slack import Action, encode_value
from src.models.split import SplitResult

Blocks = list[dict[str, Any]]


def yen(amount: int) -> str:
    return f"{amount:,}円"


def _when(dt: datetime) -> str:
    return f"{dt.month}/{dt.day} {dt:%H:%M}"


def _button(text: str, action: Action, value: dict[str, Any], style: str | None = None) -> dict:
    button: dict[str, Any] = {
        "type": "button",
        "text": {"type": "plain_text", "text": text},
        "action_id": action.value,
        "value": encode_value(value),
    }
    if style:
        button["style"] = style
    return button


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


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
    blocks: Blocks = [
        _section(f"*{title}*\n日時: {_when(event.datetime)}\n幹事: {organizer.display_name}"),
        _section(
            "*支払いの委任（同意の内容）*\n"
            f"• 上限: *{yen(cap_yen)}* まで\n"
            f"• 支払先: 幹事の {organizer.display_name} さんだけ\n"
            f"• 期限: {expires_at:%Y/%m/%d} まで\n"
            "• 按分の承認のあと、あなたの支払いエージェントが、この範囲で振込を依頼します。"
            "実際の振込は、*銀行の承認ページで、あなたが承認したときだけ*実行されます。\n"
            "• 振込の依頼が作られる前なら、App Home からいつでも取り消せます。"
        ),
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
