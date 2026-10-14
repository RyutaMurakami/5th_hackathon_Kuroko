"""架空の会社「株式会社Akakura」の人物と数字（review 04。TASKS E8）。テストとデモの投入が使う。"""

import datetime as dt

from src.models.event import Event, Participant, ParticipantRole, Preferences

EVENT_DATE = dt.datetime(2026, 10, 30, 19, 0)


# 開催希望駅（駅すぱあとの `verify_station` で確かめた駅コードと駅名。TASKS B18・O6）。
# 聞くのは、**幹事・赤坂 くらお・赤くら 花子の3人だけ**（ほかの参加者は聞かない。2026-10-15）。
# 店の候補は、この3人の希望から、駅すぱあとで全員が行きやすい駅を計算して探す
STATION = {
    "kanji": ("22741", "新宿"),
    "kurao": ("22715", "渋谷"),
    "hanako": ("23368", "横浜"),
}


def person(user_id, title, hire, emp, role=ParticipantRole.PARTICIPANT, **kw) -> Participant:
    if user_id in STATION and "preferences" not in kw:
        code, name = STATION[user_id]
        kw["preferences"] = Preferences(nearest_station_code=code, nearest_station_name=name)
    return Participant(
        user_id=user_id,
        display_name=kw.pop("display_name", user_id),
        job_title=title,
        hire_date=dt.date.fromisoformat(hire),
        employee_id=emp,
        employment_type=kw.pop("employment_type", "正社員"),
        role=role,
        attendance_confirmed=kw.pop("attending", True),
        **kw,
    )


# 表示名。画面と Slack に出て操作するのは、幹事（Web にログインした人）と、Slack に実在する2人
# （赤坂 くらお・赤くら 花子）だけ。ほかの人は、10人の歓送迎会にするための架空の参加者（SPEC 7.6）
NAMES = {
    "kanji": "幹事",
    "kurao": "赤坂 くらお",
    "hanako": "赤くら 花子",
    "sasaki": "佐々木（課長）",
    "watanabe": "渡辺",
    "nakamura": "中村",
    "kobayashi": "小林",
    "kato": "加藤（新人）",
    "matsumoto": "松本（歓迎）",
    "inoue": "井上（送別）",
}

# Web のチャット画面に列がある登場人物（SPEC 7.7）
PERSONAS = {"kurao", "hanako"}

# 出欠のカードの入力欄（開催希望駅・苦手な食べ物）に、はじめから入れておくデモ用の値（SPEC 7.7）
DEMO_ANSWERS = {
    "kurao": {"station": "渋谷", "dislikes": "えびが苦手です"},
    "hanako": {"station": "横浜", "dislikes": ""},
}


def demo_participants() -> list[Participant]:
    """歓送迎会の出席者10名（review 04 4章。配役は SPEC 7.6）。"""
    people = [
        person("hanako", "部長", "2008-04-01", "E001"),  # 承認者（規程で決まる）
        person("sasaki", "課長", "2012-04-01", "E014"),
        person("kanji", "一般", "2019-04-01", "E101", role=ParticipantRole.ORGANIZER),
        person("kurao", "一般", "2020-04-01", "E102"),
        person("watanabe", "一般", "2021-04-01", "E103"),
        person("nakamura", "一般", "2021-10-01", "E104"),
        person("kobayashi", "一般", "2022-04-01", "E105"),
        person("kato", "一般", "2026-04-01", "E201"),  # 入社1年未満
        person("matsumoto", "一般", "2026-09-01", "E202", role=ParticipantRole.GUEST_OF_HONOR),
        person("inoue", "一般", "2018-04-01", "E099", role=ParticipantRole.GUEST_OF_HONOR),
    ]
    return [
        p.model_copy(
            update={"display_name": NAMES[p.user_id], "demo_persona": p.user_id in PERSONAS}
        )
        for p in people
    ]


def demo_event(total=60_300) -> Event:
    return Event(
        event_id="ev-demo",
        datetime=EVENT_DATE,
        organizer_user_id="kanji",
        guests_of_honor=["matsumoto", "inoue"],
        total_amount_yen=total,
    )
