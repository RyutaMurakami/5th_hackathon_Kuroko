"""過去の会の記憶（seed）を、Memory Bank に入れる（SPEC 9.8「デモ」。human_task H27）。

入れるのは、`services/memory_facts.py` の**定型の文だけ**（自由な文は入れられない）。店名は、
店の候補（Google Maps）に出る名前と同じにする（同じ店名のときだけ、候補の理由と順位に効く）。

使い方（リポジトリの `backend/` で。ADC に、Memory Bank に書ける権限が要る）:
  MEMORY_BANK_ENGINE=projects/<番号>/locations/us-central1/reasoningEngines/<ID> \\
    uv run python scripts/seed_memory.py "店名" --year 2026 --month 6 --per-person 5200 \\
      --party 10 --rating 4.3 --responses 8 --reuse yes
  （`--dry-run` を付けると、書き込まずに文面だけを出す）
"""

import argparse
import asyncio

from src.clients.memory_bank import VertexMemoryBank
from src.config import get_settings
from src.services.memory_facts import TEAM_SCOPE, evaluation_fact, is_template_fact, record_fact


def build(a: argparse.Namespace) -> list[str]:
    base = {
        "event_type": "welcome_farewell", "year": a.year, "month": a.month, "venue_name": a.venue,
    }  # fmt: skip
    facts = [
        record_fact(
            **base, party_size=a.party, per_person_yen=a.per_person, course_price_yen=a.course,
            within_budget=a.per_person <= a.limit,
        )  # fmt: skip
    ]
    if a.rating is not None:
        facts.append(
            evaluation_fact(
                **base, avg_rating=a.rating, response_count=a.responses, reuse_intent=a.reuse
            )
        )
    assert all(is_template_fact(f) for f in facts)
    return facts


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("venue")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--party", type=int, default=10)
    p.add_argument("--per-person", type=int, required=True)
    p.add_argument("--course", type=int, default=None)
    p.add_argument("--limit", type=int, default=7000)  # 規程の1人あたりの上限
    p.add_argument("--rating", type=float, default=None)
    p.add_argument("--responses", type=int, default=8)
    p.add_argument("--reuse", choices=["yes", "no", "unanswered"], default="unanswered")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    facts = build(a)
    for f in facts:
        print(f)
    if a.dry_run:
        return
    engine = get_settings().memory_bank_engine
    if not engine:
        raise SystemExit("MEMORY_BANK_ENGINE を設定してください")
    bank = VertexMemoryBank(engine=engine)
    for f in facts:
        print("saved:", (await bank.create(TEAM_SCOPE, f)).rsplit("/", 1)[-1])


if __name__ == "__main__":
    asyncio.run(main())
