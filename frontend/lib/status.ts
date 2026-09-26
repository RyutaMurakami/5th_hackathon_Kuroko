// 状態 → 表示（文字と色）の対応。DESIGN.md「Status Pill」の表を1か所に置く。
import type {
  ConsentState,
  DecisionActionType,
  EventStatus,
  NotificationKind,
  ParticipantRole,
  PaymentStatus,
  RetroStatus,
} from "./types";

/** Navy = システムが進行中 / Sun = 人の対応待ち / Lagoon = 完了 / Coral = 失敗 / Slate = 対象外 */
export type Tone = "navy" | "sun" | "lagoon" | "coral" | "slate";

export type StatusView = { label: string; tone: Tone };

export const EVENT_STATUS: Record<EventStatus, StatusView> = {
  planning: { label: "企画中", tone: "slate" },
  rsvp: { label: "出欠収集中", tone: "navy" },
  venue: { label: "店舗選定中", tone: "navy" },
  booked: { label: "予約済み", tone: "navy" },
  day_of: { label: "開催当日", tone: "navy" },
  receipt: { label: "領収書の確定待ち", tone: "sun" },
  split: { label: "按分中", tone: "navy" },
  approval: { label: "承認待ち", tone: "sun" },
  payment: { label: "送金中", tone: "navy" },
  completed: { label: "完了", tone: "lagoon" },
  retro: { label: "振り返り中", tone: "navy" },
  closed: { label: "終了", tone: "lagoon" },
};

export const EVENT_STATUS_ORDER: EventStatus[] = [
  "planning",
  "rsvp",
  "venue",
  "booked",
  "day_of",
  "receipt",
  "split",
  "approval",
  "payment",
  "completed",
  "retro",
  "closed",
];

export const PAYMENT_STATUS: Record<PaymentStatus, StatusView> = {
  not_applicable: { label: "対象外", tone: "slate" },
  waiting: { label: "待機", tone: "slate" },
  awaiting_bank_approval: { label: "銀行での承認待ち", tone: "sun" },
  completed: { label: "送金済み", tone: "lagoon" },
  blocked: { label: "ブロック", tone: "coral" },
  failed: { label: "失敗", tone: "coral" },
};

export const CONSENT_STATE: Record<ConsentState, StatusView> = {
  pending: { label: "承諾待ち", tone: "sun" },
  bank_auth_pending: { label: "銀行の認可待ち", tone: "sun" },
  consented: { label: "承諾済み", tone: "lagoon" },
  revoked: { label: "取り消し済み", tone: "sun" },
  awaiting_bank_approval: { label: "銀行での承認待ち", tone: "sun" },
  paid: { label: "送金済み", tone: "lagoon" },
  stopped: { label: "止まっている", tone: "coral" },
  expired: { label: "期限切れ", tone: "slate" },
  declined: { label: "辞退", tone: "slate" },
  not_applicable: { label: "対象外", tone: "slate" },
};

/** Consent List の並び順（DESIGN.md: 承諾待ち → 銀行の認可待ち → 取り消し済み → 承諾済み → 対象外） */
export const CONSENT_SORT: Record<ConsentState, number> = {
  pending: 0,
  bank_auth_pending: 1,
  stopped: 2,
  awaiting_bank_approval: 3,
  revoked: 4,
  consented: 5,
  paid: 6,
  expired: 7,
  declined: 8,
  not_applicable: 9,
};

export const RETRO_STATUS: Record<RetroStatus, StatusView> = {
  collecting: { label: "収集中", tone: "navy" },
  awaiting_organizer: { label: "幹事の確認待ち", tone: "sun" },
  saved: { label: "記憶に保存済み", tone: "lagoon" },
  skipped: { label: "保存しない", tone: "slate" },
  expired: { label: "期限切れ", tone: "slate" },
};

export const ACTION_TYPE_TONE: Record<DecisionActionType, Tone> = {
  ブロック: "coral",
  待機: "sun",
  署名: "lagoon",
  確認: "lagoon",
  判断: "navy",
  規程: "navy",
  ツール: "navy",
  照会: "navy",
  検査: "slate",
  マスキング: "slate",
  送信: "slate",
  更新: "slate",
  記録: "slate",
};

export const NOTIFICATION_KIND: Record<NotificationKind, StatusView> = {
  confirm_needed: { label: "確認待ち", tone: "sun" },
  waiting_on_human: { label: "Slack で対応待ち", tone: "sun" },
  completed: { label: "完了", tone: "lagoon" },
  blocked: { label: "ブロック", tone: "coral" },
  retro_ready: { label: "振り返り", tone: "sun" },
};

export const PARTICIPANT_ROLE_LABEL: Record<ParticipantRole, string> = {
  organizer: "幹事",
  approver: "承認者",
  participant: "参加者",
  guest_of_honor: "主役",
};

export const MEMBER_CLASS_LABEL: Record<string, string> = {
  director: "部長",
  manager: "マネージャー",
  staff: "メンバー",
  new_hire: "新入社員",
};

/** DESIGN.md「Flow Stepper」: Event.status を7つの段階にまとめる */
export const FLOW_STEPS: { label: string; statuses: EventStatus[] }[] = [
  { label: "出欠・承諾", statuses: ["planning", "rsvp"] },
  { label: "店舗・予約", statuses: ["venue", "booked"] },
  { label: "開催", statuses: ["day_of"] },
  { label: "精算", statuses: ["receipt", "split", "approval"] },
  { label: "送金", statuses: ["payment"] },
  { label: "完了", statuses: ["completed"] },
  { label: "振り返り", statuses: ["retro", "closed"] },
];

export function flowStepIndex(status: EventStatus): number {
  return FLOW_STEPS.findIndex((step) => step.statuses.includes(status));
}

/** status 以降か（例: split 以降で按分の内訳を出す） */
export function isAtOrAfter(status: EventStatus, target: EventStatus): boolean {
  return EVENT_STATUS_ORDER.indexOf(status) >= EVENT_STATUS_ORDER.indexOf(target);
}
