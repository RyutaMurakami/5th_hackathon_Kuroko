// kuroko-api の `/api/dashboard/*` が返す形（backend/src/services/dashboard.py と同じ。snake_case）。
// 画面の表示用の型（lib/types.ts）への変換は、データ取得層で行う。

export type ApiRole = "organizer" | "guest";

/** 画面の種類。experience: 審査員の体験用（Web だけで進める）。live: 開発者の実演用（Slack と本物の銀行） */
export type ApiUiMode = "experience" | "live";

export type ApiMe = {
  role: ApiRole;
  /** 実演用の画面（本物の銀行に振込を依頼する）を使えるアカウントか */
  live_allowed: boolean;
  /** イベントを作る前の進行ヒント */
  start_hints: Record<ApiUiMode, ApiHint>;
};

export type ApiVenueCandidate = {
  place_id: string;
  name: string;
  address: string;
  nearest_station: string;
  max_travel_minutes: number;
  avg_travel_minutes: number;
  price_min_yen: number | null;
  price_max_yen: number | null;
  features: string[];
  rating: number | null;
  /** 選んだ理由（コードが作った事実からの定型の文） */
  selection_reason: string;
  /** 記憶に基づく理由（同じ店の過去の実績。無ければ null） */
  memory_note: string | null;
};

export type ApiEventSummary = {
  event_id: string;
  title: string;
  datetime: string;
  status: string;
  sandbox: boolean;
  ui_mode: ApiUiMode;
};

export type ApiMessage = {
  message_id: string;
  event_id: string;
  role: "organizer" | "kuroko" | "system";
  text: string;
  status: "pending" | "done" | "failed" | "blocked";
  /** この発言の位置に出す、状態つきのカードの種類（時系列を崩さないため。画面は同じ種類のうち最後の発言に出す） */
  card?: "plan" | "venues" | "split" | "transfer" | "retro" | null;
  created_at: string;
};

export type ApiUpload = {
  upload_id: string;
  kind: "reservation" | "receipt";
  status: "issued" | "registered" | "rejected";
  extraction_status: "pending" | "done" | "failed";
  content_type: string;
  created_at: string;
  /** 読み取り結果（幹事が確認するまで使われない） */
  extraction?: {
    venue_name: string | null;
    warnings: string[];
    /** 領収書（`ocr_receipt`） */
    date?: string | null;
    total_amount_yen?: number | null;
    line_items?: { name: string; unit_price_yen: number | null; quantity: number | null; amount_yen: number | null }[];
    /** 予約画面（`ingest_reservation`） */
    datetime?: string | null;
    party_size?: number | null;
    course_price_yen?: number | null;
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
  ui_mode: ApiUiMode;
  /** 店の候補（出欠が出そろうと、KUROKO が自分で探す。順位はコードが決める） */
  venue_candidates: ApiVenueCandidate[];
  /** 店の検索の進み具合（searching のあいだ「探しています」を出す。failed なら、探し直せる） */
  venue_search: { status: "" | "searching" | "done" | "failed"; error: string };
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
  /** 登場人物の振込を、どこで承認するか（web: 体験用のボタン。bank: 本物の銀行） */
  bank_approval: "web" | "bank";
  /** 登場人物ごとの、KUROKO から届いたカード（体験用のイベントだけ。SPEC 7.7） */
  personas: ApiPersona[];
  /** 振り返りの集計と、覚えさせる事実の下書き（個人ごとの回答は含まない。SPEC 9.8） */
  retro: ApiRetro | null;
};

export type ApiMemoryFact = {
  kind: "venue_record" | "venue_evaluation";
  /** 定型の文（編集できない。含める・含めないだけ） */
  text: string;
  include: boolean;
  saved: boolean;
};

export type ApiRetro = {
  status: "collecting" | "awaiting_organizer" | "saved" | "skipped" | "expired";
  invited_count: number;
  response_count: number;
  avg_rating: number | null;
  liked_counts: Record<string, number>;
  concern_counts: Record<string, number>;
  venue_name: string;
  party_size: number;
  per_person_yen: number | null;
  within_budget: boolean | null;
  reuse_intent: "yes" | "no" | "unanswered";
  memory_facts: ApiMemoryFact[];
  saved_at: string | null;
};

/** KUROKO から登場人物に届いたカード（Slack の DM と同じ中身）。ボタンの値は、サーバーが持つ */
export type ApiPersonaCard = {
  card_id: string;
  /** notice は、ボタンの無いお知らせ（開催の案内） */
  kind: "consent" | "approval" | "budget" | "bank" | "feedback" | "notice";
  text: string;
  /** 本文（Slack の mrkdwn。`*太字*`・改行・`• 箇条書き`） */
  sections: string[];
  buttons: { index: number; label: string; style: string }[];
  resolved_text: string | null;
  created_at: string;
  /** 体験用の「銀行で承認する」のカード（押すと、銀行の承認ページを模した画面を挟む） */
  bank?: boolean;
  /** 出欠のカードの入力欄（最寄り駅・苦手な食べ物）。値は、デモ用の候補 */
  fields?: ApiCardField[];
};

export type ApiCardField = { key: "station" | "dislikes"; label: string; value: string; placeholder: string };

/** 計画のカードに、はじめから入れておく値（`hint.example.plan`。架空） */
export type ApiPlanExample = {
  title?: string;
  /** `datetime-local` の形（例: 2026-10-30T19:00） */
  datetime?: string;
  party_size?: number;
  budget_per_person_yen?: number;
  rsvp_deadline?: string;
  /** 主役に選べる人（名簿の主役は `locked` で、外せない） */
  honorees?: { user_id: string; display_name: string; selected: boolean; locked: boolean }[];
};

export type ApiPersona = {
  user_id: string;
  display_name: string;
  job_title: string;
  cards: ApiPersonaCard[];
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
  /** 根拠の規程（どこから取った値か・値のまとまりごとの条。SPEC 9.7） */
  policy?: {
    policy_id: string;
    version: string;
    source: "document" | "yaml";
    citations: Record<string, string>;
  } | null;
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
  party_size: number;
  budget_per_person_yen: number;
  required_tags: string[];
  /** 出欠の回答期限（YYYY-MM-DD。任意） */
  rsvp_deadline?: string;
  /** 幹事が足す主役（名簿の user_id） */
  guests_of_honor?: string[];
};

/** KUROKO が参照している情報（記憶と規程。SPEC 7.9） */
export interface ApiReference {
  memory: {
    available: boolean;
    error: string;
    groups: { label: string; facts: { text: string; created: string }[] }[];
  };
  policy: {
    title: string;
    policy_id: string;
    version: string;
    source: "document" | "yaml";
    articles: { number: string; heading: string; text: string }[];
    values: {
      member_classes: { label: string; weight: number; consent_cap_yen: number }[];
      subsidy_per_attendee_yen: number;
      subsidy_max_per_event_yen: number;
      rounding_unit_yen: number;
      hard_limit_per_person_yen: number;
      approver_selection: string[];
      venue_max_travel_minutes: number;
    };
    citations: Record<string, string>;
  };
}
