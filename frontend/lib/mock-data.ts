// バックエンド（/api/dashboard/*）につなぐまでのダミーデータ（TASKS T1.14）。
// 登場人物と金額は docs/review/2026-09-13_KUROKO_review_04_story.md（すべて架空）。
// 按分の数字は calculate_split の結果を写したもので、Web では再計算しない（SPEC 7.3.1）。
import { isAtOrAfter } from "./status";
import type {
  ActivityItem,
  AppNotification,
  ChatMessage,
  ConsentState,
  DecisionLogEntry,
  EventDetail,
  EventStatus,
  EventSummary,
  Extraction,
  Handoff,
  MemberClass,
  Participant,
  ParticipantRole,
  Payment,
  Retrospective,
  Role,
  SplitResult,
  VenueCandidate,
  Worker,
} from "./types";

type Person = {
  userId: string;
  name: string;
  role: ParticipantRole;
  memberClass: MemberClass | null;
  weight: number;
  shareYen: number;
  capYen: number | null;
};

const PEOPLE: Person[] = [
  { userId: "u-yamada", name: "山田 健一", role: "approver", memberClass: "director", weight: 2.0, shareYen: 7200, capYen: 12000 },
  { userId: "u-sasaki", name: "佐々木 真理", role: "participant", memberClass: "manager", weight: 1.5, shareYen: 5000, capYen: 9000 },
  { userId: "u-takahashi", name: "高橋 翔", role: "organizer", memberClass: "staff", weight: 1.0, shareYen: 3300, capYen: null },
  { userId: "u-ito", name: "伊藤 彩", role: "participant", memberClass: "staff", weight: 1.0, shareYen: 3300, capYen: 6000 },
  { userId: "u-watanabe", name: "渡辺 大輔", role: "participant", memberClass: "staff", weight: 1.0, shareYen: 3300, capYen: 6000 },
  { userId: "u-nakamura", name: "中村 美咲", role: "participant", memberClass: "staff", weight: 1.0, shareYen: 3300, capYen: 6000 },
  { userId: "u-kobayashi", name: "小林 蓮", role: "participant", memberClass: "staff", weight: 1.0, shareYen: 3300, capYen: 6000 },
  { userId: "u-kato", name: "加藤 陽菜", role: "participant", memberClass: "new_hire", weight: 0.5, shareYen: 1600, capYen: 3000 },
  { userId: "u-matsumoto", name: "松本 拓也", role: "guest_of_honor", memberClass: null, weight: 0, shareYen: 0, capYen: null },
  { userId: "u-inoue", name: "井上 由紀", role: "guest_of_honor", memberClass: null, weight: 0, shareYen: 0, capYen: null },
];

const ORGANIZER_ID = "u-takahashi";
const APPROVER_ID = "u-yamada";
const PAYERS = PEOPLE.filter((p) => p.role === "participant" || p.role === "approver");
const MANDATE_EXPIRES_AT = "2026-11-06T23:59:00+09:00";

type EventSeed = {
  eventId: string;
  title: string;
  datetime: string;
  companyName: string;
  teamName: string;
  defaultStatus: EventStatus;
  sandbox: boolean;
};

const EVENTS: EventSeed[] = [
  {
    eventId: "evt-2026-1030",
    title: "歓送迎会（松本さん・井上さん）",
    datetime: "2026-10-30T19:00:00+09:00",
    companyName: "サンプル株式会社",
    teamName: "営業部 第2課",
    defaultStatus: "payment",
    sandbox: false,
  },
  {
    eventId: "evt-2026-1009",
    title: "歓迎会（新任マネージャー）",
    datetime: "2026-10-09T18:30:00+09:00",
    companyName: "サンプル株式会社",
    teamName: "営業部 第1課",
    defaultStatus: "approval",
    sandbox: false,
  },
  {
    eventId: "evt-2026-1120",
    title: "送別会（期末の異動）",
    datetime: "2026-11-20T19:00:00+09:00",
    companyName: "サンプル株式会社",
    teamName: "営業部 第2課",
    defaultStatus: "rsvp",
    sandbox: false,
  },
  {
    eventId: "evt-2026-0626",
    title: "歓送迎会（6月）",
    datetime: "2026-06-26T19:00:00+09:00",
    companyName: "サンプル株式会社",
    teamName: "営業部 第2課",
    defaultStatus: "closed",
    sandbox: false,
  },
  {
    eventId: "sandbox-demo",
    title: "歓送迎会（体験用）",
    datetime: "2026-10-30T19:00:00+09:00",
    companyName: "サンプル商事",
    teamName: "営業部",
    defaultStatus: "planning",
    sandbox: true,
  },
];

/** 開発者の画面は仮名（User_001）。API が実名の表を引かない想定（ARCHITECTURE 4.5） */
function nameFor(role: Role) {
  return (userId: string): string => {
    const index = PEOPLE.findIndex((p) => p.userId === userId);
    if (role === "developer") return `User_${String(index + 1).padStart(3, "0")}`;
    return PEOPLE[index]?.name ?? userId;
  };
}

/** 「山田さん」の形。開発者には仮名のまま */
function sanFor(role: Role) {
  const name = nameFor(role);
  return (userId: string): string =>
    role === "developer" ? name(userId) : `${name(userId).split(" ")[0]}さん`;
}

function consentFor(person: Person, status: EventStatus): ConsentState {
  if (person.role === "organizer" || person.role === "guest_of_honor") return "not_applicable";
  if (status === "planning") return "pending";
  if (status === "rsvp") {
    const rsvp: Record<string, ConsentState> = {
      "u-nakamura": "pending",
      "u-kato": "pending",
      "u-watanabe": "bank_auth_pending",
    };
    return rsvp[person.userId] ?? "consented";
  }
  if (status === "payment") {
    return PENDING_BANK.includes(person.userId) ? "awaiting_bank_approval" : "paid";
  }
  if (isAtOrAfter(status, "completed")) return "paid";
  return "consented";
}

const PENDING_BANK = ["u-kobayashi", "u-kato"];

function buildParticipants(status: EventStatus, role: Role): Participant[] {
  if (status === "planning") return [];
  const name = nameFor(role);
  return PEOPLE.map((p) => ({
    userId: p.userId,
    displayName: name(p.userId),
    role: p.role,
    memberClass: p.memberClass,
    consent: consentFor(p, status),
    capYen: p.capYen,
    mandateExpiresAt: p.capYen ? MANDATE_EXPIRES_AT : null,
  }));
}

function buildPayments(status: EventStatus): Payment[] {
  if (!isAtOrAfter(status, "split")) return [];
  return PAYERS.map((p, i) => {
    let paymentStatus: Payment["status"] = "waiting";
    let approvalDeadline: string | null = null;
    let retryCount = 0;
    let updatedAt: string | null = null;
    if (status === "payment") {
      if (PENDING_BANK.includes(p.userId)) {
        paymentStatus = "awaiting_bank_approval";
        approvalDeadline = p.userId === "u-kobayashi" ? "2026-11-02T10:24:00+09:00" : "2026-11-02T10:27:00+09:00";
        retryCount = p.userId === "u-kobayashi" ? 1 : 0;
        updatedAt = p.userId === "u-kobayashi" ? "2026-11-02T10:14:00+09:00" : "2026-11-02T10:17:00+09:00";
      } else {
        paymentStatus = "completed";
        updatedAt = `2026-11-02T10:0${i + 3}:00+09:00`;
      }
    } else if (isAtOrAfter(status, "completed")) {
      paymentStatus = "completed";
      updatedAt = `2026-11-02T10:${String(i * 3 + 3).padStart(2, "0")}:00+09:00`;
    }
    return {
      paymentId: `pay-${p.userId}`,
      payerUserId: p.userId,
      payeeUserId: ORGANIZER_ID,
      amountYen: p.shareYen,
      status: paymentStatus,
      approvalDeadline,
      retryCount,
      blockReason: null,
      updatedAt,
    };
  });
}

function buildSplit(status: EventStatus): SplitResult | null {
  if (!isAtOrAfter(status, "split")) return null;
  const approved = isAtOrAfter(status, "payment");
  return {
    totalAmountYen: 60300,
    subsidyYen: 30000,
    baseAmountYen: 30300,
    weightSum: 9.0,
    perWeightYen: 3366,
    rows: PEOPLE.map((p) => ({
      userId: p.userId,
      memberClass: p.memberClass,
      weight: p.weight,
      subsidyEligible: true,
      shareYen: p.shareYen,
      billed: p.role === "participant" || p.role === "approver",
    })),
    shareTotalYen: 30300,
    shortfallYen: 500,
    shortfallTo: APPROVER_ID,
    policyQuotes: [
      {
        article: "規程 第7条（負担の係数）",
        text: "懇親会の費用は、会社補助を差し引いた額を、区分ごとの係数（部長 2.0、課長 1.5、一般 1.0、入社1年未満 0.5）で按分する。主役は負担しない。",
      },
      {
        article: "規程 第8条（会社補助）",
        text: "会社は、出席者1人あたり3,000円（主役を含む）を補助する。1回の上限は60,000円とする。",
      },
      {
        article: "規程 第9条（端数）",
        text: "各人の負担額は100円未満を切り捨て、不足分は承認者が負担する。",
      },
    ],
    approval: {
      approverUserId: APPROVER_ID,
      status: approved ? "approved" : "pending",
      approvedAt: approved ? "2026-11-02T09:58:00+09:00" : null,
      splitHash: "9f3a61c2d84b7e05a1c3",
    },
  };
}

const VENUE_CANDIDATES: VenueCandidate[] = [
  {
    candidateId: "v-kodama",
    name: "炉端 こだま 神田店",
    area: "神田",
    pricePerPersonMin: 4500,
    pricePerPersonMax: 5500,
    maxTravelMinutes: 38,
    avgTravelMinutes: 24,
    features: ["個室", "飲み放題"],
    memoryNote: "前回の歓送迎会で、個室の評価が高かった（5名が「個室」を良かった点に選択）",
    memoryPeriod: "2026/06",
  },
  {
    candidateId: "v-akari",
    name: "ビストロ 灯 有楽町",
    area: "有楽町",
    pricePerPersonMin: 5000,
    pricePerPersonMax: 6000,
    maxTravelMinutes: 42,
    avgTravelMinutes: 27,
    features: ["半個室"],
    memoryNote: null,
    memoryPeriod: null,
  },
  {
    candidateId: "v-maruya",
    name: "和食 まるや 東京駅前",
    area: "東京",
    pricePerPersonMin: 4000,
    pricePerPersonMax: 5000,
    maxTravelMinutes: 44,
    avgTravelMinutes: 29,
    features: ["個室", "駅直結"],
    memoryNote: null,
    memoryPeriod: null,
  },
];

function buildReservation(status: EventStatus): Extraction | null {
  if (!isAtOrAfter(status, "venue")) return null;
  return {
    kind: "reservation",
    fileName: "reservation_kodama.png",
    fields: [
      { key: "venue_name", label: "店名", value: "炉端 こだま 神田店", kind: "text", placeholder: "例: 炉端 こだま 神田店" },
      { key: "datetime", label: "日時", value: "10/30（金）19:00", kind: "text", placeholder: "例: 10/30（金）19:00" },
      { key: "party_size", label: "人数", value: "10", kind: "number", unit: "名", placeholder: "例: 10" },
      { key: "course_price_yen", label: "コース単価", value: "5500", kind: "yen", unit: "円", placeholder: "例: 5500" },
    ],
    confirmedAt: isAtOrAfter(status, "booked") ? "2026-10-02T12:40:00+09:00" : null,
  };
}

function buildReceipt(status: EventStatus): Extraction | null {
  if (!isAtOrAfter(status, "receipt")) return null;
  return {
    kind: "receipt",
    fileName: "receipt_kodama.jpg",
    fields: [
      { key: "venue_name", label: "店名", value: "炉端 こだま 神田店", kind: "text", placeholder: "例: 炉端 こだま 神田店" },
      { key: "date", label: "日付", value: "2026/10/30", kind: "text", placeholder: "例: 2026/10/30" },
      { key: "total_amount_yen", label: "合計金額", value: "60300", kind: "yen", unit: "円", placeholder: "例: 60300" },
    ],
    confirmedAt: isAtOrAfter(status, "split") ? "2026-10-31T09:12:00+09:00" : null,
  };
}

function buildRetro(status: EventStatus, teamName: string): Retrospective | null {
  if (!isAtOrAfter(status, "retro")) return null;
  const saved = status === "closed";
  return {
    status: saved ? "saved" : "awaiting_organizer",
    invitedCount: 10,
    responseCount: 7,
    avgRating: 4.3,
    likedCounts: [
      { label: "個室", count: 5 },
      { label: "料理", count: 4 },
      { label: "アクセス", count: 3 },
    ],
    concernCounts: [
      { label: "騒がしい", count: 2 },
      { label: "提供が遅い", count: 1 },
    ],
    memoryFacts: [
      {
        factId: "f-venue",
        kind: "venue_evaluation",
        text: `${teamName}の歓送迎会（2026/10）で『炉端 こだま 神田店』（神田・個室）を利用。満足度は平均4.3（7名回答）。良かった点は個室・料理。気になった点は騒がしさ。`,
        include: true,
      },
      {
        factId: "f-budget",
        kind: "budget_trend",
        text: `${teamName}の歓送迎会（2026/10）の1人あたりの会計は6,030円（コース5,500円）。`,
        include: true,
      },
    ],
    savedAt: saved ? "2026-11-06T09:30:00+09:00" : null,
  };
}

type Timed<T> = T & { from: EventStatus };

function upTo<T>(items: Timed<T>[], status: EventStatus): T[] {
  return items.filter((item) => isAtOrAfter(status, item.from)).map(({ from: _from, ...rest }) => rest as T);
}

function buildMessages(status: EventStatus, role: Role, seed: EventSeed): ChatMessage[] {
  const san = sanFor(role);
  const planConfirmed = isAtOrAfter(status, "rsvp");
  const messages: Timed<ChatMessage>[] = [
    {
      from: "planning",
      messageId: "m1",
      role: "organizer",
      createdAt: "2026-09-22T10:02:00+09:00",
      text: `10/30（金）19時から、${san("u-matsumoto")}の歓迎と${san("u-inoue")}の送別をやりたい。部署のみんなで`,
    },
    {
      from: "planning",
      messageId: "m2",
      role: "kuroko",
      createdAt: "2026-09-22T10:02:30+09:00",
      text: `歓送迎会として進めます。対象は${seed.teamName}の10名でよいですか？ エリアの希望と、出欠の回答期限を教えてください。`,
    },
    {
      from: "planning",
      messageId: "m3",
      role: "organizer",
      createdAt: "2026-09-22T10:04:00+09:00",
      text: "10名で。神田か有楽町あたり。回答は10/16まで",
    },
    {
      from: "planning",
      messageId: "m4",
      role: "kuroko",
      createdAt: "2026-09-22T10:04:40+09:00",
      text: "条件を整理しました。内容を確認して、よければ進めてください。確定すると、Slack で参加者に出欠と支払いの委任の依頼が届きます。",
      proposal: {
        items: [
          { label: "種別", value: "歓送迎会" },
          { label: "日時", value: "10/30（金）19:00" },
          { label: "人数", value: "10名（主役 2名を含む）" },
          { label: "エリア", value: "神田・有楽町" },
          { label: "予算の目安", value: "1人 4,000〜6,000円（規程 第5条）" },
          { label: "承認者の見込み", value: `${nameFor(role)(APPROVER_ID)}（部長）` },
          { label: "出欠の回答期限", value: "10/16（金）" },
        ],
        confirmedAt: planConfirmed ? "2026-09-22T10:06:00+09:00" : null,
      },
    },
    {
      from: "rsvp",
      messageId: "m5",
      role: "kuroko",
      createdAt: "2026-09-22T10:06:20+09:00",
      text: "出欠と支払いの委任の依頼を、Slack で参加者 7名に送りました。主役の2名には、費用の話を含まない案内を送っています。",
    },
    {
      from: "venue",
      messageId: "m6",
      role: "kuroko",
      createdAt: "2026-10-01T09:00:00+09:00",
      text: "全員が45分以内に来られるエリアで、3件の候補を見つけました。前回の歓送迎会で個室の評価が高かったので、個室のある店を先頭にしています。",
    },
    {
      from: "booked",
      messageId: "m7",
      role: "kuroko",
      createdAt: "2026-10-02T12:41:00+09:00",
      text: "予約内容を確定しました。コース 5,500円は、規程の上限（1人 7,000円）以内です。",
    },
    {
      from: "receipt",
      messageId: "m8",
      role: "kuroko",
      createdAt: "2026-10-31T09:00:00+09:00",
      text: "おつかれさまでした。領収書をアップロードしてください。金額を読み取るので、確認をお願いします。",
    },
    {
      from: "split",
      messageId: "m9",
      role: "kuroko",
      createdAt: "2026-10-31T09:13:00+09:00",
      text: `領収書の金額 60,300円で按分しました。承認者の${san(APPROVER_ID)}に、Slack で承認を依頼しています。`,
    },
    {
      from: "payment",
      messageId: "m10",
      role: "kuroko",
      createdAt: "2026-11-02T09:58:30+09:00",
      text: `${san(APPROVER_ID)}が按分を承認しました。7名の支払いエージェントが、委任の範囲内で振込を依頼しています。`,
    },
    {
      from: "completed",
      messageId: "m11",
      role: "kuroko",
      createdAt: "2026-11-02T10:30:00+09:00",
      text: "全員の入金を明細で確認しました。振込で 27,000円を回収しました。経費精算の記録（PDF）を用意しています。",
    },
    {
      from: "retro",
      messageId: "m12",
      role: "kuroko",
      createdAt: "2026-11-06T09:00:00+09:00",
      text: "振り返りがまとまりました（7名が回答）。次回に覚えさせる内容を確認してください。",
    },
  ];
  return upTo(messages, status);
}

function buildActivity(status: EventStatus, role: Role, sandbox: boolean): ActivityItem[] {
  const san = sanFor(role);
  const items: Timed<ActivityItem>[] = [
    { from: "planning", at: "2026-09-22T10:02:10+09:00", text: "規程を確認しました（歓送迎会・第5条）", state: "done" },
    { from: "planning", at: "2026-09-22T10:02:20+09:00", text: "過去の記憶を参照しました（2026/06 の歓送迎会）", state: "done" },
    { from: "planning", at: "2026-09-22T10:04:40+09:00", text: "幹事の条件の確認を待っています", state: "waiting" },
    { from: "rsvp", at: "2026-09-22T10:06:20+09:00", text: "Slack で出欠と委任の依頼を送りました（7名）", state: "done" },
    { from: "rsvp", at: "2026-09-24T09:00:00+09:00", text: "回答を集めています（残り 3名）", state: "waiting" },
    { from: "venue", at: "2026-10-01T08:58:00+09:00", text: "全員の帰りやすさを計算しました（最も遠い人でも 38分）", state: "done" },
    { from: "venue", at: "2026-10-01T09:00:00+09:00", text: "店舗の候補を 3件見つけました。幹事の選択を待っています", state: "waiting" },
    { from: "booked", at: "2026-10-02T12:41:00+09:00", text: "予約内容を確定しました（上限の確認済み）", state: "done" },
    { from: "day_of", at: "2026-10-30T18:30:00+09:00", text: "出席を確認しています", state: "progress" },
    { from: "receipt", at: "2026-10-31T09:00:00+09:00", text: "領収書のアップロードを待っています", state: "waiting" },
    { from: "split", at: "2026-10-31T09:12:30+09:00", text: "按分を計算しました（規程 第7〜9条）", state: "done" },
    { from: "approval", at: "2026-10-31T09:13:00+09:00", text: `${san(APPROVER_ID)}の承認を Slack で待っています`, state: "waiting" },
    { from: "payment", at: "2026-11-02T09:59:00+09:00", text: "7件の振込を依頼しました（委任の範囲内）", state: "done" },
    { from: "payment", at: "2026-11-02T10:14:00+09:00", text: `${san("u-kobayashi")}の依頼を作り直しました（期限切れ・1回目）`, state: "done" },
    { from: "payment", at: "2026-11-02T10:18:00+09:00", text: "銀行での承認を 2名分待っています", state: "waiting" },
    { from: "completed", at: "2026-11-02T10:30:00+09:00", text: "全員の入金を明細で確認しました", state: "done" },
    { from: "retro", at: "2026-11-06T09:00:00+09:00", text: "振り返りを集計しました。幹事の確認を待っています", state: "waiting" },
    { from: "closed", at: "2026-11-06T09:30:00+09:00", text: "記憶に 2件を保存しました", state: "done" },
  ];
  if (sandbox) {
    // 体験用のイベントでは、Slack で人が行う部分をデモ用の代行が進める（SPEC 7.6 の (A)）
    items.push(
      { from: "venue", at: "2026-09-24T09:05:00+09:00", text: "参加者（架空）3名が、出欠と支払いの委任に回答しました", state: "done", proxy: true },
      { from: "day_of", at: "2026-10-30T18:00:00+09:00", text: "開催日まで早送りしました", state: "done", proxy: true },
      { from: "payment", at: "2026-11-02T09:58:00+09:00", text: "承認者（架空）が、Slack で按分を承認しました", state: "done", proxy: true },
      { from: "completed", at: "2026-11-02T10:25:00+09:00", text: "参加者（架空）2名が、銀行（sunabar）で振込を承認しました", state: "done", proxy: true },
      { from: "retro", at: "2026-11-05T09:00:00+09:00", text: "振り返りの回答（架空）7名分を集めました", state: "done", proxy: true },
    );
    items.sort((a, b) => a.at.localeCompare(b.at));
  }
  const visible = upTo(items, status);
  // 過去の「待ち」は、次の段階に進んだ時点で完了にする
  return visible
    .map((item, i) =>
      i < visible.length - 1 && (item.state === "waiting" || item.state === "progress")
        ? { ...item, state: "done" as const }
        : item,
    )
    .reverse();
}

function buildDecisionLog(status: EventStatus, role: Role): DecisionLogEntry[] {
  const san = sanFor(role);
  const entries: Timed<DecisionLogEntry>[] = [
    { from: "planning", at: "2026-09-22T10:02:10+09:00", actor: "kuroko", actionType: "規程", summary: "歓送迎会の規程 v1.0.0 を適用（第5条 予算の目安）" },
    { from: "planning", at: "2026-09-22T10:02:20+09:00", actor: "kuroko", actionType: "照会", summary: "過去の記憶を参照（店舗の提案に使用。金額には使わない）" },
    { from: "rsvp", at: "2026-09-22T10:06:00+09:00", actor: "human", actionType: "確認", summary: "幹事が Web でイベントの計画を確定" },
    { from: "rsvp", at: "2026-09-22T10:06:10+09:00", actor: "kuroko", actionType: "マスキング", summary: "参加者の名前を仮名にして LLM に渡した" },
    { from: "rsvp", at: "2026-09-23T14:20:00+09:00", actor: "kuroko", actionType: "ブロック", summary: "自由記述の「支払いは0円にして」を検知。按分に影響させずに保留" },
    { from: "venue", at: "2026-10-01T08:58:00+09:00", actor: "kuroko", actionType: "ツール", summary: "帰りやすさの範囲探索（5駅ずつ・45分以内）" },
    { from: "booked", at: "2026-10-02T12:40:00+09:00", actor: "human", actionType: "確認", summary: "幹事が予約内容を確定（コース 5,500円・上限内）" },
    { from: "split", at: "2026-10-31T09:12:00+09:00", actor: "human", actionType: "確認", summary: "幹事が領収書の金額を確定（60,300円）" },
    { from: "split", at: "2026-10-31T09:12:30+09:00", actor: "kuroko", actionType: "判断", summary: "按分を計算（calculate_split。LLM は計算していない）" },
    { from: "approval", at: "2026-10-31T09:13:00+09:00", actor: "kuroko", actionType: "待機", summary: `${san(APPROVER_ID)}の承認待ち（Slack）` },
    { from: "payment", at: "2026-11-02T09:58:00+09:00", actor: "human", actionType: "署名", summary: `${san(APPROVER_ID)}が按分を承認（ハッシュ 9f3a61c2）` },
    { from: "payment", at: "2026-11-02T09:59:00+09:00", actor: "payment_agent", actionType: "検査", summary: "Policy Gate 6.3 を通過（上限・支払先・期限・nonce）" },
    { from: "payment", at: "2026-11-02T09:59:10+09:00", actor: "payment_agent", actionType: "送信", summary: "振込依頼 7件（sunabar）" },
    { from: "completed", at: "2026-11-02T10:30:00+09:00", actor: "payment_agent", actionType: "確認", summary: "入出金明細で 7件の入金を確認" },
    { from: "closed", at: "2026-11-06T09:30:00+09:00", actor: "human", actionType: "記録", summary: "幹事が確認した 2件を記憶に保存（Policy Gate 6.4）" },
  ];
  return upTo(entries, status).reverse();
}

function buildHandoff(status: EventStatus, role: Role, sandbox: boolean): Handoff | null {
  const san = sanFor(role);
  const name = nameFor(role);
  const proxy = (text: string) => (sandbox ? text : null);
  if (status === "rsvp") {
    return {
      who: `参加者 3名（${san("u-nakamura")}・${san("u-kato")}・${san("u-watanabe")}）`,
      what: "が、Slack で出欠と支払いの委任に回答する必要があります",
      detail: `${san("u-watanabe")}は委任に同意済みで、銀行（sunabar）の認可が残っています。回答の期限は 10/16（金）です。`,
      demoProxy: proxy("デモ用の代行：架空の参加者が回答します"),
    };
  }
  if (status === "approval") {
    return {
      who: `${name(APPROVER_ID)}（承認者）`,
      what: "が、Slack で按分を承認する必要があります",
      detail: "承認すると、7名の支払いエージェントが委任の範囲内で振込を依頼します",
      demoProxy: proxy("デモ用の代行：架空の承認者が承認します"),
    };
  }
  if (status === "payment") {
    return {
      who: `${san("u-kobayashi")}・${san("u-kato")}`,
      what: "が、銀行（sunabar）の承認ページで振込を承認する必要があります",
      detail: "依頼から10分以内に承認がないと、KUROKOが依頼を作り直します（最大2回）",
      demoProxy: proxy("デモ用の代行：架空の参加者が銀行で承認します"),
    };
  }
  return null;
}

function waitingOnFor(status: EventStatus, role: Role): string | null {
  const san = sanFor(role);
  const map: Partial<Record<EventStatus, string>> = {
    planning: "幹事の条件の確認待ち",
    rsvp: "参加者 3名の回答待ち（Slack）",
    venue: "幹事の店舗の選択と予約待ち",
    receipt: "幹事の領収書の確定待ち",
    approval: `承認者 ${san(APPROVER_ID)}の対応待ち（Slack）`,
    payment: "2名の銀行での承認待ち",
    retro: "幹事の振り返りの確認待ち",
  };
  return map[status] ?? null;
}

const AGENT = {
  kuroko: { name: "KUROKO Agent", role: "統括" },
  extract: { name: "隔離抽出 Agent", role: "ツールを持たない" },
} as const;

const NO_LLM = "LLM は使っていません";

/** エージェントと仕組みを区別して、いま誰が何をしているかを段階ごとに返す（PLAN 12章の3つのエージェント） */
function buildWorkers(status: EventStatus, role: Role): Worker[] {
  const san = sanFor(role);
  const kuroko = (id: string, action: string, state: Worker["state"]): Worker => ({
    id, kind: "agent", ...AGENT.kuroko, action, state,
  });
  const extract = (id: string, action: string, state: Worker["state"]): Worker => ({
    id, kind: "agent", ...AGENT.extract, action, state,
  });
  const system = (id: string, name: string, action: string, state: Worker["state"], roleText = NO_LLM): Worker => ({
    id, kind: "system", name, role: roleText, action, state,
  });
  const payer = (userId: string, action: string, state: Worker["state"]): Worker => ({
    id: `payer-${userId}`, kind: "agent", name: `${san(userId)}の支払い Agent`, role: "参加者の代理", action, state,
  });

  const byStatus: Record<EventStatus, Worker[]> = {
    planning: [
      kuroko("k", "依頼の内容を読んで、足りない条件を確認しています", "running"),
      system("rag", "規程の検索", "歓送迎会の規程（予算の目安・係数）を引いています", "running", "RAG Engine。LLM の外の仕組み"),
    ],
    rsvp: [
      extract("x", "参加者の自由記述（好み・最寄り駅）を、決まった形式の値だけに変えています", "running"),
      kuroko("k", "出欠と委任がそろうのを待っています", "waiting"),
    ],
    venue: [
      system("route", "帰りやすさの計算", "全員が45分以内に来られるエリアを探しました", "done"),
      kuroko("k", "候補の店を提案し、過去の記憶を根拠に添えています", "running"),
      extract("x", "口コミの本文を、決まった形式の値だけに変えました", "done"),
    ],
    booked: [
      system("budget", "予算チェック", "コース単価を規程の上限と照らしました", "done"),
      kuroko("k", "開催日の出席確認の準備をしています", "running"),
    ],
    day_of: [kuroko("k", "参加者の出席を確認しています", "running")],
    receipt: [
      kuroko("k", "領収書の読み取り結果を、幹事が確定するのを待っています", "waiting"),
    ],
    split: [
      system("split", "按分の計算", "規程の係数で、一人ひとりの負担額を出しています", "running"),
      system("gate", "Policy Gate", "按分を確定する前の項目を検査しています", "running"),
      kuroko("k", "按分の根拠を、規程の条文つきで説明する文を作っています", "running"),
    ],
    approval: [
      kuroko("k", "承認者の承認を待っています", "waiting"),
      system("gate", "Policy Gate", "按分の検査を通しました（承認後に、請求を出す前の検査をします）", "done"),
      system("split", "按分の計算", "按分表を確定しました（ハッシュ付き）", "done"),
    ],
    payment: [
      payer("u-kobayashi", "銀行での承認を待っています（作り直し 1回）", "waiting"),
      payer("u-kato", "銀行での承認を待っています", "waiting"),
      system("bank", "銀行アダプタ", "sunabar に振込の状況を照会しています", "running", "口座とトークンを持つ。LLM は使っていません"),
      {
        id: "payer-done", kind: "agent", name: "5名の支払い Agent", role: "参加者の代理",
        action: "委任の範囲内で振込を依頼し、入金を明細で確認しました", state: "done",
      },
    ],
    completed: [
      kuroko("k", "経費精算の記録（PDF）を用意しています", "running"),
      system("redact", "個人情報の削除", "好み・最寄り駅などを消しています", "running"),
    ],
    retro: [
      system("summary", "振り返りの集計", "回答を集計し、覚えさせる内容の下書きを作りました", "done"),
      extract("x", "自由記述を、決まった語彙だけに変えました（原文は捨てています）", "done"),
    ],
    closed: [],
  };
  const order = { running: 0, waiting: 1, done: 2 } as const;
  return [...byStatus[status]].sort((a, b) => order[a.state] - order[b.state]);
}

const NEXT_STEP: Record<EventStatus, string> = {
  planning: "条件を確認すると、Slack で出欠の依頼が届きます",
  rsvp: "全員がそろうと、帰りやすいお店を探します",
  venue: "お店を選んで予約したら、予約画面をアップロードします",
  booked: "開催日になったら、出席を確認します",
  day_of: "開催後に、領収書をアップロードします",
  receipt: "領収書の金額を確定すると、按分を計算します",
  split: "按分を計算しています。まもなく承認者に届きます",
  approval: "承認されると、各自の支払いエージェントが振込を依頼します",
  payment: "全員の入金を明細で確認すると完了です",
  completed: "翌日、参加者に振り返りをお願いします",
  retro: "振り返りを確認して、次回に覚えさせる内容を選びます",
  closed: "このイベントは終わりました。覚えた内容は次回の企画で使います",
};

/** 題名に主役の名前が入ることがあるので、開発者には括弧の中を出さない（仮名のみ。SPEC 7.3） */
function titleFor(seed: EventSeed, role: Role): string {
  if (role !== "developer") return seed.title;
  return seed.title.replace(/（.*）$/, `（${seed.eventId}）`);
}

function seedOf(eventId: string): EventSeed | undefined {
  return EVENTS.find((e) => e.eventId === eventId);
}

export function isEventStatus(value: string | null | undefined): value is EventStatus {
  return (
    !!value &&
    ["planning", "rsvp", "venue", "booked", "day_of", "receipt", "split", "approval", "payment", "completed", "retro", "closed"].includes(value)
  );
}

export function getEventDetail(eventId: string, role: Role, stage?: EventStatus): EventDetail | null {
  const seed = seedOf(eventId);
  if (!seed) return null;
  if (!canSee(seed, role)) return null;
  const status = stage ?? seed.defaultStatus;
  const participants = buildParticipants(status, role);
  const payments = buildPayments(status);
  const payers = participants.filter((p) => p.role === "participant" || p.role === "approver");
  const consentedCount = payers.filter((p) =>
    ["consented", "awaiting_bank_approval", "paid"].includes(p.consent),
  ).length;
  return {
    eventId: seed.eventId,
    title: titleFor(seed, role),
    datetime: seed.datetime,
    organizerName: nameFor(role)(ORGANIZER_ID),
    status,
    consentedCount,
    consentTargetCount: payers.length,
    paidYen: payments.filter((p) => p.status === "completed").reduce((sum, p) => sum + p.amountYen, 0),
    billedYen: payments.reduce((sum, p) => sum + p.amountYen, 0),
    sandbox: seed.sandbox,
    companyName: seed.companyName,
    venueName: isAtOrAfter(status, "booked") ? "炉端 こだま 神田店" : null,
    waitingOn: waitingOnFor(status, role),
    nextStep: NEXT_STEP[status],
    workers: buildWorkers(status, role),
    participants,
    payments,
    split: buildSplit(status),
    venueCandidates: status === "venue" ? VENUE_CANDIDATES : [],
    reservation: buildReservation(status),
    receipt: buildReceipt(status),
    retrospective: buildRetro(status, seed.teamName),
    messages: role === "developer" ? [] : buildMessages(status, role, seed),
    activity: buildActivity(status, role, seed.sandbox),
    decisionLog: buildDecisionLog(status, role),
    handoff: buildHandoff(status, role, seed.sandbox),
  };
}

/** 範囲は API 側で強制する想定。ここではダミーで同じ振る舞いをまねる（SPEC 7.3） */
function canSee(seed: EventSeed, role: Role): boolean {
  if (role === "guest") return seed.sandbox;
  if (role === "organizer") return !seed.sandbox;
  return true;
}

export function listEvents(role: Role): EventSummary[] {
  return EVENTS.filter((seed) => canSee(seed, role))
    .map((seed) => getEventDetail(seed.eventId, role))
    .filter((detail): detail is EventDetail => detail !== null)
    .map((detail) => ({
      eventId: detail.eventId,
      title: detail.title,
      datetime: detail.datetime,
      organizerName: detail.organizerName,
      status: detail.status,
      consentedCount: detail.consentedCount,
      consentTargetCount: detail.consentTargetCount,
      paidYen: detail.paidYen,
      billedYen: detail.billedYen,
      sandbox: detail.sandbox,
    }));
}

export function listNotifications(role: Role): AppNotification[] {
  if (role === "developer") return [];
  if (role === "guest") {
    return [
      {
        notificationId: "n-g1",
        eventId: "sandbox-demo",
        kind: "confirm_needed",
        text: "イベントの計画を確認してください",
        createdAt: "2026-09-22T10:04:40+09:00",
        read: false,
      },
    ];
  }
  return [
    {
      notificationId: "n1",
      eventId: "evt-2026-1030",
      kind: "waiting_on_human",
      text: "2名の銀行での承認を待っています（歓送迎会）",
      createdAt: "2026-11-02T10:18:00+09:00",
      read: false,
    },
    {
      notificationId: "n2",
      eventId: "evt-2026-1009",
      kind: "waiting_on_human",
      text: "承認者の按分の承認を Slack で待っています（歓迎会）",
      createdAt: "2026-10-10T09:13:00+09:00",
      read: false,
    },
    {
      notificationId: "n3",
      eventId: "evt-2026-1120",
      kind: "blocked",
      text: "回答の自由記述に不正な指示があったため、保留しました（送別会）",
      createdAt: "2026-09-23T14:20:00+09:00",
      read: true,
    },
    {
      notificationId: "n4",
      eventId: "evt-2026-0626",
      kind: "completed",
      text: "記憶に 2件を保存しました（歓送迎会・6月）",
      createdAt: "2026-07-02T09:30:00+09:00",
      read: true,
    },
  ];
}

export function defaultEventIdFor(role: Role): string {
  return role === "guest" ? "sandbox-demo" : "evt-2026-1030";
}
