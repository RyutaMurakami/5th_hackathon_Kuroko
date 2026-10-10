"""規程の値（`policy_snapshot`。SPEC 3章 Event・9.7節）。

企画時に規程（RAG Engine。使えないときは `policies/company_rules.yaml`）から取り出した値を
コードで検証したもの。**按分・承認者の決定は、この写しだけを使う**（再抽出しない）。
LLM は値を読み取るだけで、計算には使わない（`audit.llm_must_not`）。
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# approver_selection に書ける比較の名前（SPEC 6章・規程の approval.approver_selection）
APPROVER_RULES = ("highest_weight", "highest_rank", "earliest_hire_date", "lowest_employee_id")


class MemberClass(BaseModel):
    id: str
    label: str
    # 区分の判定（上から順に評価し、最初に一致したものを使う）
    role: str
    tenure_months_less_than: int | None = None
    rank: int = Field(ge=0)
    weight: float = Field(ge=0, le=3)  # 規程の係数。範囲外は値の検証（B4）で差し戻す
    consent_cap_yen: int = Field(ge=0, le=20_000)


class Subsidy(BaseModel):
    per_attendee_yen: int = Field(ge=0)
    include_guests_of_honor: bool
    max_per_event_yen: int = Field(ge=0)
    eligible_employment_types: list[str]


class PolicySnapshot(BaseModel):
    policy_id: str
    version: str
    member_classes: list[MemberClass] = Field(min_length=1)
    subsidy: Subsidy
    rounding_unit_yen: int = Field(gt=0)
    rounding_method: Literal["floor"] = "floor"
    shortfall_to: Literal["approver"] = "approver"
    approver_selection: list[str] = Field(min_length=1)
    hard_limit_per_person_yen: int = Field(gt=0)
    # 委任状の有効期限（開催日から数えた日数。payment.payer_mandate.expires_after_event_days）
    mandate_valid_days_after_event: int = Field(default=7, gt=0, le=30)

    @model_validator(mode="after")
    def _check(self) -> "PolicySnapshot":
        ids = [c.id for c in self.member_classes]
        if len(set(ids)) != len(ids):
            raise ValueError("member class ids must be unique")
        unknown = [r for r in self.approver_selection if r not in APPROVER_RULES]
        if unknown:
            raise ValueError(f"unknown approver_selection: {unknown}")
        return self

    def member_class(self, class_id: str) -> MemberClass:
        for c in self.member_classes:
            if c.id == class_id:
                return c
        raise KeyError(class_id)
