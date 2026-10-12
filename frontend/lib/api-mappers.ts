// API の形（snake_case。lib/api-types.ts）→ 画面の表示用の型（lib/types.ts）。
// API に無いもの（エージェントの稼働・経緯・読み取り結果など）は、空にして、無いことを正直に見せる。
import type { ApiEventDetail, ApiEventSummary, ApiNotification } from "./api-types";
import type {
  AppNotification,
  ConsentState,
  EventDetail,
  EventStatus,
  EventSummary,
  DecisionActionType,
  Participant,
  ParticipantRole,
  Payment,
  PaymentStatus,
  SplitResult,
} from "./types";

const STATUSES: EventStatus[] = [
  "planning", "rsvp", "venue", "booked", "day_of", "receipt",
  "split", "approval", "payment", "completed", "retro", "closed",
]; // prettier-ignore

function status(s: string): EventStatus {
  return (STATUSES as string[]).includes(s) ? (s as EventStatus) : "planning";
}

export function toEventSummary(e: ApiEventSummary): EventSummary {
  return {
    eventId: e.event_id,
    title: e.title || "（題名未定）",
    datetime: e.datetime,
    organizerName: "あなた",
    status: status(e.status),
    consentedCount: 0,
    consentTargetCount: 0,
    paidYen: 0,
    billedYen: 0,
    sandbox: e.sandbox,
  };
}

function consent(role: string, rsvp: string, signed: boolean): ConsentState {
  if (role === "organizer" || role === "guest_of_honor") return "not_applicable";
  if (rsvp === "declining") return "declined";
  if (rsvp === "attending" && signed) return "consented";
  return "pending";
}

function toSplit(s: NonNullable<ApiEventDetail["split"]>): SplitResult {
  return {
    totalAmountYen: s.total_amount_yen,
    subsidyYen: s.subsidy_yen,
    baseAmountYen: s.base_amount_yen,
    weightSum: s.weight_sum,
    perWeightYen: s.per_weight_yen,
    rows: s.rows.map((r) => ({
      userId: r.user_id,
      memberClass: null,
      weight: r.weight,
      subsidyEligible: r.subsidy_eligible,
      shareYen: r.share_yen,
      billed: r.share_yen > 0,
    })),
    shareTotalYen: s.rows.reduce((sum, r) => sum + r.share_yen, 0),
    shortfallYen: s.shortfall_yen,
    shortfallTo: s.shortfall_to || null,
    policyQuotes: [], // 規程の引用は API がまだ返さない
    approval: {
      approverUserId: s.approval.approver_user_id,
      status: s.approval.status === "approved" ? "approved" : "pending",
      approvedAt: s.approval.approved_at,
      splitHash: s.approval.split_hash,
    },
  };
}

const PAYMENT_STATUSES: PaymentStatus[] = [
  "not_applicable", "waiting", "awaiting_bank_approval", "completed", "blocked", "failed",
]; // prettier-ignore

function toPayments(e: ApiEventDetail): Payment[] {
  return e.payments.map((p) => ({
    paymentId: p.payment_id,
    payerUserId: p.payer_user_id,
    payeeUserId: p.payee_user_id,
    amountYen: p.amount_yen,
    status: (PAYMENT_STATUSES as string[]).includes(p.status) ? (p.status as PaymentStatus) : "waiting",
    approvalDeadline: p.approval_deadline,
    retryCount: p.retry_count ?? 0,
    blockReason: p.block_reason,
    updatedAt: p.updated_at,
  }));
}

export function toEventDetail(e: ApiEventDetail): EventDetail {
  const participants: Participant[] = e.participants.map((p) => ({
    userId: p.user_id,
    displayName: p.display_name || p.user_id,
    role: p.role as ParticipantRole,
    memberClass: null,
    consent: consent(p.role, p.rsvp_status, p.mandate_signed),
    capYen: null,
    mandateExpiresAt: null,
  }));
  const payers = participants.filter((p) => p.role === "participant" || p.role === "approver");
  const organizer = participants.find((p) => p.role === "organizer");
  const venueName = typeof e.venue?.name === "string" ? e.venue.name : typeof e.venue?.venue_name === "string" ? e.venue.venue_name : null;
  const w = e.waiting_for;
  const payments = toPayments(e);
  return {
    eventId: e.event_id,
    title: e.title || "（題名未定）",
    datetime: e.datetime,
    organizerName: organizer?.displayName ?? "あなた",
    status: status(e.status),
    consentedCount: payers.filter((p) => p.consent === "consented").length,
    consentTargetCount: payers.length,
    paidYen: payments.filter((p) => p.status === "completed").reduce((sum, p) => sum + p.amountYen, 0),
    billedYen: e.split ? e.split.rows.reduce((sum, r) => sum + r.share_yen, 0) : 0,
    sandbox: e.sandbox,
    companyName: e.sandbox ? "株式会社Akakura（体験用）" : "",
    venueName,
    waitingOn: w ? `${w.what}（${w.where === "slack" ? "Slack" : w.where === "bank" ? "銀行" : "Web"}）` : null,
    nextStep: e.hint.title,
    workers: [],
    participants,
    payments,
    split: e.split ? toSplit(e.split) : null,
    venueCandidates: [],
    reservation: null,
    receipt: null,
    retrospective: null,
    messages: e.messages.map((m) => ({
      messageId: m.message_id,
      role: m.role,
      text: m.text,
      createdAt: m.created_at,
    })),
    activity: [],
    decisionLog: e.decision_log.map((d) => ({
      at: d.at,
      actor: d.actor,
      actionType: d.action_type as DecisionActionType,
      summary: d.summary,
    })),
    handoff:
      w && w.where !== "web"
        ? { who: w.who, what: w.what, detail: e.hint.do, demoProxy: null }
        : null,
  };
}

export function toNotification(n: ApiNotification): AppNotification {
  return {
    notificationId: n.notification_id,
    eventId: n.event_id,
    kind: (
      { confirm_needed: "confirm_needed", slack_waiting: "waiting_on_human", completed: "completed", blocked: "blocked", retro_ready: "retro_ready" } as const
    )[n.kind],
    text: n.text,
    createdAt: n.created_at,
    read: n.read,
  };
}
