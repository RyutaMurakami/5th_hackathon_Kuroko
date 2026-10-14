"""実演用の幹事に、Slack の DM で操作を渡す（SPEC 7.8）。

実演（動画）では、幹事の操作（お店選び・予約画面と領収書の画像・予算超過の確認・按分の承認依頼・
振込の依頼の承認・振り返りの確認）を、Web ではなく Slack の DM で行う。ここは、その DM（本文と
ボタン）を作って送るだけで、状態は変えない（状態を変えるのは、ボタンを受ける
`DashboardService.slack_op`）。体験用（`experience`）のイベントには、何も送らない。
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from src.db.events import EventStore
from src.models.event import Event
from src.models.slack import Action
from src.services.slack_messages import Blocks, _button, _section, maps_url, yen

logger = logging.getLogger(__name__)

MAX_VENUE_BUTTONS = 5


class _Poster(Protocol):
    async def post_dm(self, slack_user_id: str, text: str, blocks: list[dict]) -> None: ...


EmailLookup = Callable[[str], Awaitable[str | None]]  # メール → Slack ユーザーID


def _op(event: Event, slack_id: str, op: str, **extra: Any) -> dict[str, Any]:
    """幹事の操作ボタンの値。`s` は宛先の Slack ユーザー（本人だけが押せる）。"""
    return {"k": "org", "o": op, "e": event.event_id, "s": slack_id, **extra}


def _actions(*buttons: dict) -> dict:
    return {"type": "actions", "elements": list(buttons)}


class OrganizerDM:
    def __init__(
        self, *, store: EventStore, slack: _Poster, find_by_email: EmailLookup | None = None
    ) -> None:
        self._store, self._slack, self._find = store, slack, find_by_email

    async def target(self, event: Event) -> str | None:
        """この幹事の Slack ユーザーID。実演用のイベントで、結びつく人がいるときだけ。"""
        if event.ui_mode != "live":
            return None
        if event.organizer_slack_user_id:
            return event.organizer_slack_user_id
        email = event.organizer_email.lower()
        if not email:
            return None
        for slack_id, mapped in self._store.live_slack_users().items():
            if mapped.lower() == email:
                found: str | None = slack_id
                break
        else:
            found = None
            if self._find is not None:
                try:
                    found = await self._find(email)
                except Exception:
                    logger.info("could not find the Slack user by email")
        if found:  # 次からは、この人だけが操作できる（確認の基準になる）
            self._store.save_event(event.model_copy(update={"organizer_slack_user_id": found}))
        return found

    async def _send(self, event: Event, text: str, blocks: Blocks | None = None) -> bool:
        slack_id = await self.target(event)
        if not slack_id:
            return False
        try:
            await self._slack.post_dm(slack_id, text, blocks or [_section(text)])
        except Exception:  # Slack の失敗で、進行を止めない（Web の画面にも同じ内容が出る）
            logger.exception("could not DM the organizer: event=%s", event.event_id)
            return False
        return True

    async def _slack_id(self, event: Event) -> str | None:
        return await self.target(event)

    # ---- 場面ごとの DM ----
    async def say(self, event: Event, text: str) -> None:
        await self._send(event, text)

    async def venues(self, event: Event) -> None:
        slack_id = await self._slack_id(event)
        if not slack_id or not event.venue_candidates:
            return
        shown = event.venue_candidates[:MAX_VENUE_BUTTONS]
        people = [
            p for p in self._store.list_participants(event.event_id) if p.attendance_confirmed
        ]
        stations = {
            p.preferences.nearest_station_code for p in people if p.preferences.nearest_station_code
        }
        lines = [
            f"参加者 {len(people)}人の最寄り駅（{len(stations)}駅）から、全員が行きやすい駅を"
            "駅すぱあとで調べました。",
            "*お店の候補です*（全員の最寄り駅からの帰りやすさ・苦手な食べ物・過去の実績で順位を付けています）",
        ]
        for n, c in enumerate(shown, start=1):
            price = (
                f"{yen(int(c['price_min_yen']))}〜{yen(int(c['price_max_yen']))}"
                if c.get("price_min_yen") and c.get("price_max_yen")
                else ""
            )
            station = f"{c.get('nearest_station')}駅・" if c.get("nearest_station") else ""
            url = maps_url(str(c.get("name", "")), str(c.get("place_id", "")))
            lines.append(
                f"{n}. *{c.get('name')}*（{station}最大{c.get('max_travel_minutes', '?')}分"
                f"{'・' + price if price else ''}・<{url}|Google マップ>）\n"
                f"　{c.get('selection_reason', '')}"
            )
        buttons = [
            _button(
                f"{n}. {str(c.get('name'))[:40]}",
                Action.ORG,
                _op(event, slack_id, "venue", p=str(c.get("place_id", ""))),
                "primary" if n == 1 else None,
                mark=f"venue{n}",
            )
            for n, c in enumerate(shown, start=1)
        ]
        text = "お店の候補が見つかりました。1つ選んでください"
        await self._send(event, text, [_section("\n".join(lines)), _actions(*buttons)])

    async def reservation_prompt(self, event: Event, name: str) -> None:
        await self._send(
            event,
            f"「{name}」ですね。お店への予約をお願いします（予約は、幹事さんがお店で行います）。"
            "予約が済んだら、*予約完了の画面（スクリーンショット）を、このDMに画像で送って*ください。",
        )

    async def extraction(self, event: Event, kind: str, upload_id: str, data: dict) -> None:
        slack_id = await self._slack_id(event)
        if not slack_id:
            return
        if kind == "reservation":
            lines = [
                "*予約の画面を読み取りました*。次の内容でよければ、確定してください。",
                f"お店: {data.get('venue_name')}",
                f"日時: {data.get('datetime')}",
                f"人数: {data.get('party_size')}名",
                f"コース: {yen(int(data.get('course_price_yen') or 0))}／人",
            ]
        else:
            lines = [
                "*領収書を読み取りました*。金額がよければ、確定してください。",
                f"合計金額: {yen(int(data.get('total_amount_yen') or 0))}",
            ]
        for w in data.get("warnings") or []:
            lines.append(f"（注意）{w}")
        value = _op(event, slack_id, "extract", kd=kind, u=upload_id)
        await self._send(
            event,
            "読み取った内容を確かめてください",
            [
                _section("\n".join(lines)),
                _actions(_button("この内容で確定する", Action.ORG, value, "primary")),
            ],
        )

    async def held_prompt(self, event: Event) -> None:
        slack_id = await self._slack_id(event)
        if not slack_id:
            return
        await self._send(
            event,
            "開催が終わったら、教えてください",
            [
                _section(
                    "予約が確定しました。参加者に開催の案内を送っています。\n"
                    "開催が終わったら、下のボタンを押してください（そのあと、領収書の画像を送ります）。"
                ),
                _actions(
                    _button("開催が終わった", Action.ORG, _op(event, slack_id, "held"), "primary")
                ),
            ],
        )

    async def budget(self, event: Event, price: int, limit: int) -> None:
        slack_id = await self._slack_id(event)
        if not slack_id:
            return
        await self._send(
            event,
            "予算超過です。続行するか確認してください",
            [
                _section(
                    f"コース単価（{yen(price)}）が、規程の上限（{yen(limit)}）を超えています。"
                    "続行する場合は、承認者に最終確認を依頼します。"
                ),
                _actions(
                    _button(
                        "続行して、承認者に確認を依頼する",
                        Action.ORG,
                        _op(event, slack_id, "budget"),
                        "primary",
                    )
                ),
            ],
        )

    async def receipt_prompt(self, event: Event) -> None:
        await self._send(
            event,
            "お疲れさまでした。*お店の領収書の写真を、このDMに画像で送って*ください。"
            "金額を読み取って、確認のカードをお出しします。",
        )

    async def split(self, event: Event, lines: list[str], approver_name: str) -> None:
        slack_id = await self._slack_id(event)
        if not slack_id:
            return
        body = "*按分の内訳です*（会社の規程で計算しました）\n" + "\n".join(lines)
        await self._send(
            event,
            "按分の内訳を確かめてください",
            [
                _section(body),
                _section(
                    f"確かめて、規程で決まる承認者の {approver_name} さんに承認を依頼してください。"
                ),
                _actions(
                    _button(
                        "承認者に承認を依頼する",
                        Action.ORG,
                        _op(event, slack_id, "split"),
                        "primary",
                    )
                ),
            ],
        )

    async def transfers(self, event: Event, approver_name: str) -> None:
        slack_id = await self._slack_id(event)
        if not slack_id:
            return
        await self._send(
            event,
            "振込の依頼を送るか、確認してください",
            [
                _section(
                    f"承認者の {approver_name} さんが、按分を承認しました。\n"
                    "参加者に、振込の依頼（各自が銀行で承認するもの）を送ってよいですか？"
                ),
                _actions(
                    _button(
                        "振込の依頼を送る", Action.ORG, _op(event, slack_id, "transfers"), "primary"
                    )
                ),
            ],
        )

    async def retro(self, event: Event, summary: str) -> None:
        slack_id = await self._slack_id(event)
        if not slack_id:
            return
        await self._send(
            event,
            "振り返りがまとまりました",
            [
                _section(summary),
                _section("次回のために、会の実績（お店・評価）を記憶に残しますか？"),
                _actions(
                    _button(
                        "また使いたい（記憶に残す）",
                        Action.ORG,
                        _op(event, slack_id, "retro", ri="yes", d="save"),
                        "primary",
                        mark="yes",
                    ),
                    _button(
                        "使わない（記憶に残す）",
                        Action.ORG,
                        _op(event, slack_id, "retro", ri="no", d="save"),
                        None,
                        mark="no",
                    ),
                    _button(
                        "記憶に残さない",
                        Action.ORG,
                        _op(event, slack_id, "retro", ri="unanswered", d="skip"),
                        None,
                        mark="skip",
                    ),
                ),
            ],
        )
