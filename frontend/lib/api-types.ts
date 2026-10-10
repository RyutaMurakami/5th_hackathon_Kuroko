// kuroko-api の `/api/dashboard/*` が返す形（backend/src/services/dashboard.py と同じ。snake_case）。
// 画面の表示用の型（lib/types.ts）への変換は、データ取得層で行う。

export type ApiRole = "organizer" | "guest";

export type ApiEventSummary = {
  event_id: string;
  title: string;
  datetime: string;
  status: string;
  sandbox: boolean;
};

export type ApiMessage = {
  message_id: string;
  event_id: string;
  role: "organizer" | "kuroko" | "system";
  text: string;
  status: "pending" | "done" | "failed" | "blocked";
  created_at: string;
};

export type ApiUpload = {
  upload_id: string;
  kind: "reservation" | "receipt";
  status: "issued" | "registered" | "rejected";
  extraction_status: "pending" | "done" | "failed";
  content_type: string;
  /** 読み取り結果（幹事が確認するまで使われない） */
  extraction?: {
    venue_name: string | null;
    date: string | null;
    total_amount_yen: number | null;
    line_items: { name: string; unit_price_yen: number | null; quantity: number | null; amount_yen: number | null }[];
    warnings: string[];
  } | null;
};

/** 進行ヒント（SPEC 7.5）。案内だけで、操作の代行ではない */
export type ApiHint = {
  step: number;
  total: number;
  where: "web" | "slack" | "bank" | "system";
  who: string;
  title: string;
  do: string;
  example: Record<string, unknown> | null;
};

export type ApiEventDetail = {
  event_id: string;
  title: string;
  datetime: string;
  status: string;
  sandbox: boolean;
  plan: Record<string, unknown>;
  venue: Record<string, unknown> | null;
  total_amount_yen: number | null;
  participants: {
    user_id: string;
    display_name: string;
    role: string;
    rsvp_status: string;
    mandate_signed: boolean;
  }[];
  uploads: ApiUpload[];
  messages: ApiMessage[];
  waiting_for: { who: string; where: string; what: string; users?: string[] } | null;
  hint: ApiHint;
  /** 保存された SplitResult の値そのまま（再計算しない） */
  split: ApiSplit | null;
  /** 予約のコース単価が規程の上限を超えているときだけ入る（SPEC 9.1） */
  budget_overrun: {
    course_price_yen: number;
    limit_yen: number;
    organizer_confirmed: boolean;
    approver_confirmed: boolean;
  } | null;
  payments: ApiPayment[];
  decision_log: ApiDecision[];
};

export type ApiPayment = {
  payment_id: string;
  payer_user_id: string;
  payee_user_id: string;
  amount_yen: number;
  status: string;
  approval_deadline: string | null;
  retry_count: number | null;
  block_reason: string | null;
  updated_at: string | null;
};

export type ApiDecision = {
  at: string;
  actor: "kuroko" | "payment_agent" | "human";
  action_type: string;
  summary: string;
};

export type ApiSplit = {
  total_amount_yen: number;
  base_amount_yen: number;
  subsidy_yen: number;
  weight_sum: number;
  per_weight_yen: number;
  shortfall_yen: number;
  shortfall_to: string;
  rows: {
    user_id: string;
    weight: number;
    ratio_percent: number;
    subsidy_eligible: boolean;
    share_yen: number;
  }[];
  approval: {
    approver_user_id: string;
    status: "pending" | "approved";
    approved_at: string | null;
    split_hash: string;
  };
};

export type ApiNotification = {
  notification_id: string;
  event_id: string;
  kind: "confirm_needed" | "slack_waiting" | "completed" | "blocked" | "retro_ready";
  text: string;
  read: boolean;
  created_at: string;
};

export type ApiPlan = {
  title: string;
  datetime: string;
  area: string;
  party_size: number;
  budget_per_person_yen: number;
  required_tags: string[];
};
