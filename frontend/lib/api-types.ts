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
};

export type ApiPlan = {
  title: string;
  datetime: string;
  area: string;
  party_size: number;
  budget_per_person_yen: number;
  required_tags: string[];
};
