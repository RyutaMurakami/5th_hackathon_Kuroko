"""架空の会社「サンプル商事」の人物と数字（review 04。TASKS E8）。テストとデモの投入が使う。"""

import datetime as dt

from src.models.event import Event, Participant, ParticipantRole, Preferences

EVENT_DATE = dt.datetime(2026, 10, 30, 19, 0)


# 最寄り駅（駅すぱあとの `verify_station` で一意に確かめた駅コード。TASKS B18・O6）。
# Web からイベントを作ると、この名簿が参加者になり、店の候補は、この駅から全員が行きやすい駅で探す
STATION = {
    "yamada": "23368",  # 横浜
    "sasaki": "21987",  # 大宮(埼玉県)
    "takahashi": "22741",  # 新宿
    "ito": "22715",  # 渋谷
    "watanabe": "22799",  # 立川
    "nakamura": "22361",  # 千葉
    "kobayashi": "22976",  # 町田
    "kato": "21982",  # 浦和
    "matsumoto": "22741",  # 新宿
    "inoue": "22715",  # 渋谷
}


def person(user_id, title, hire, emp, role=ParticipantRole.PARTICIPANT, **kw) -> Participant:
    if user_id in STATION and "preferences" not in kw:
        kw["preferences"] = Preferences(nearest_station_code=STATION[user_id])
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


def demo_participants() -> list[Participant]:
    """歓送迎会の出席者10名（review 04 4章）。"""
    return [
        person("yamada", "部長", "2008-04-01", "E001"),
        person("sasaki", "課長", "2012-04-01", "E014"),
        person("takahashi", "一般", "2019-04-01", "E101", role=ParticipantRole.ORGANIZER),
        person("ito", "一般", "2020-04-01", "E102"),
        person("watanabe", "一般", "2021-04-01", "E103"),
        person("nakamura", "一般", "2021-10-01", "E104"),
        person("kobayashi", "一般", "2022-04-01", "E105"),
        person("kato", "一般", "2026-04-01", "E201"),  # 入社1年未満
        person("matsumoto", "一般", "2026-09-01", "E202", role=ParticipantRole.GUEST_OF_HONOR),
        person("inoue", "一般", "2018-04-01", "E099", role=ParticipantRole.GUEST_OF_HONOR),
    ]


def demo_event(total=60_300) -> Event:
    return Event(
        event_id="ev-demo",
        datetime=EVENT_DATE,
        organizer_user_id="takahashi",
        guests_of_honor=["matsumoto", "inoue"],
        total_amount_yen=total,
    )
