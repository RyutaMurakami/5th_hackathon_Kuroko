// Dashboard API（kuroko-api の /api/dashboard/*）が返す形。SPEC 3章・ARCHITECTURE 4.5節。
// バックエンドにつなぐまでは lib/mock-data.ts がこの形のダミーを返す。

/** 審査員と開発者は区別しない（どちらも guest。ARCHITECTURE D25） */
export type Role = "organizer" | "guest";

export type EventStatus =
  | "planning"
  | "rsvp"
  | "venue"
  | "booked"
  | "day_of"
  | "receipt"
  | "split"
  | "approval"
  | "payment"
  | "completed"
  | "retro"
  | "closed";

export type ParticipantRole = "participant" | "organizer" | "guest_of_honor" | "approver";

export type MemberClass = "director" | "manager" | "staff" | "new_hire";

export type PaymentStatus =
  | "not_applicable"
  | "waiting"
  | "awaiting_bank_approval"
  | "completed"
  | "blocked"
  | "failed";

/** SPEC 7.3「承諾の状況の見え方」。API が導いた値をそのまま出す */
export type ConsentState =
  | "pending"
  | "bank_auth_pending"
  | "consented"
  | "revoked"
  | "awaiting_bank_approval"
  | "paid"
  | "stopped"
  | "expired"
  | "declined"
  | "not_applicable";

export type RetroStatus = "collecting" | "awaiting_organizer" | "saved" | "skipped" | "expired";

export type DecisionActionType =
  | "判断"
  | "規程"
  | "ツール"
  | "送信"
  | "照会"
  | "ブロック"
  | "検査"
  | "マスキング"
  | "記録"
  | "更新"
  | "待機"
  | "確認"
  | "署名";

export type Participant = {
  userId: string;
  /** 幹事は実名、ゲストは架空の名前（サンドボックス） */
  displayName: string;
  role: ParticipantRole;
  memberClass: MemberClass | null;
  consent: ConsentState;
  capYen: number | null;
  mandateExpiresAt: string | null;
};

export type Payment = {
  paymentId: string;
  payerUserId: string;
  payeeUserId: string;
  amountYen: number;
  status: PaymentStatus;
  /** 銀行での承認の期限（awaiting_bank_approval のとき） */
  approvalDeadline: string | null;
  retryCount: number;
  blockReason: string | null;
  updatedAt: string | null;
};

export type SplitRow = {
  userId: string;
  memberClass: MemberClass | null;
  weight: number;
  subsidyEligible: boolean;
  shareYen: number;
  /** false は「請求なし」（幹事本人・主役。SPEC 7.3.1） */
  billed: boolean;
};

export type PolicyQuote = {
  article: string;
  text: string;
};

export type SplitResult = {
  totalAmountYen: number;
  subsidyYen: number;
  baseAmountYen: number;
  weightSum: number;
  perWeightYen: number;
  rows: SplitRow[];
  shareTotalYen: number;
  shortfallYen: number;
  shortfallTo: string | null;
  policyQuotes: PolicyQuote[];
  approval: {
    approverUserId: string;
    status: "pending" | "approved";
    approvedAt: string | null;
    splitHash: string;
  };
};

export type VenueCandidate = {
  candidateId: string;
  name: string;
  area: string;
  pricePerPersonMin: number;
  pricePerPersonMax: number;
  maxTravelMinutes: number;
  avgTravelMinutes: number;
  features: string[];
  memoryNote: string | null;
  memoryPeriod: string | null;
};

export type ExtractionField = {
  key: string;
  label: string;
  value: string;
  kind: "text" | "yen" | "number";
  unit?: string;
  /** 手入力のときの入力例（値の代わりにしない） */
  placeholder?: string;
};

export type Extraction = {
  kind: "reservation" | "receipt";
  fileName: string;
  fields: ExtractionField[];
  confirmedAt: string | null;
};

export type MemoryFact = {
  factId: string;
  kind: "venue_evaluation" | "budget_trend";
  text: string;
  include: boolean;
};

export type Retrospective = {
  status: RetroStatus;
  invitedCount: number;
  responseCount: number;
  avgRating: number | null;
  /** 回答が3件未満のときは API が null を返す（内訳を出さない） */
  likedCounts: { label: string; count: number }[] | null;
  concernCounts: { label: string; count: number }[] | null;
  memoryFacts: MemoryFact[];
  savedAt: string | null;
};

export type ChatMessage = {
  messageId: string;
  role: "organizer" | "kuroko" | "system";
  text: string;
  createdAt: string;
  proposal?: EventPlanProposal;
};

export type EventPlanProposal = {
  items: { label: string; value: string }[];
  confirmedAt: string | null;
};

export type ActivityItem = {
  at: string;
  text: string;
  state: "progress" | "waiting" | "done" | "blocked";
  /** デモ用の代行（sa-demo-runner）が進めた項目。SPEC 7.6 */
  proxy?: boolean;
};

export type DecisionLogEntry = {
  at: string;
  actor: "kuroko" | "payment_agent" | "human";
  actionType: DecisionActionType;
  summary: string;
};

export type NotificationKind =
  | "confirm_needed"
  | "waiting_on_human"
  | "completed"
  | "blocked"
  | "retro_ready";

export type AppNotification = {
  notificationId: string;
  eventId: string;
  kind: NotificationKind;
  text: string;
  createdAt: string;
  read: boolean;
};

/**
 * いま動いているもの（Agent Status。DESIGN.md）。
 * agent = LLM を使うエージェント（PLAN 12章の3つ）、system = エージェントではない仕組み（コード・RAG Engine・Memory Bank）
 */
export type Worker = {
  id: string;
  kind: "agent" | "system";
  /** 「KUROKO Agent」「支払い Agent」「Policy Gate」など。支払い Agent は人ごとの名前を含む */
  name: string;
  /** 名前の下に出す役割（「統括」「LLM は使っていません」など） */
  role: string;
  /** 「が、」に続く動作（「店舗を探しています」） */
  action: string;
  state: "running" | "waiting" | "done";
};

/** Slack で人の対応が要る場面（Slack Handoff Card） */
export type Handoff = {
  who: string;
  what: string;
  detail: string;
  /** ゲストの sandbox で、デモ用の代行が有効なときの説明 */
  demoProxy: string | null;
};

export type EventSummary = {
  eventId: string;
  title: string;
  datetime: string;
  organizerName: string;
  status: EventStatus;
  consentedCount: number;
  consentTargetCount: number;
  paidYen: number;
  billedYen: number;
  sandbox: boolean;
};

export type EventDetail = EventSummary & {
  companyName: string;
  venueName: string | null;
  /** Flow Stepper の下に出す待ち相手（null は「進行中」） */
  waitingOn: string | null;
  /** 待ち相手がいないときの「次は○○です」 */
  nextStep: string;
  /** いま動いているエージェントと仕組み（新しい段階ほど先頭ではなく、動いているもの → 待ち → 済みの順） */
  workers: Worker[];
  participants: Participant[];
  payments: Payment[];
  split: SplitResult | null;
  venueCandidates: VenueCandidate[];
  reservation: Extraction | null;
  receipt: Extraction | null;
  retrospective: Retrospective | null;
  messages: ChatMessage[];
  activity: ActivityItem[];
  decisionLog: DecisionLogEntry[];
  handoff: Handoff | null;
};
