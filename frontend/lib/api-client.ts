// kuroko-api の Web 向け API（`/api/dashboard/*`）を、この画面の中継（app/api/dashboard）経由で呼ぶ。
// 利用者の確認は Firebase の ID トークン（SPEC 7.6）。権限の判定は API 側で、ここでは行わない。
import type {
  ApiEventDetail,
  ApiEventSummary,
  ApiMessage,
  ApiNotification,
  ApiPlan,
  ApiRole,
} from "./api-types";
import { getFirebaseAuth } from "./auth";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

/** API の理由コードを、画面に出す文にする。内部の事情は出さない */
const MESSAGES: Record<string, string> = {
  unauthenticated: "ログインし直してください。",
  guest_disabled: "いま体験用の利用を止めています。",
  event_not_found: "このイベントは見られません。",
  invalid_text: "発言は1〜2000文字で入力してください。",
  guest_event_limit: "体験用のイベントは2件までです。",
  guest_message_limit: "体験用の発言の上限（30通）に達しました。",
  invalid_state: "いまの段階では、この操作はできません。",
  invalid_plan: "計画の入力を確認してください（日時・人数2〜50・予算1〜100,000円など）。",
  unsupported_type: "画像（JPEG・PNG）か PDF を選んでください。",
  invalid_size: "ファイルは5MBまでです。",
  upload_limit: "このイベントのアップロードの上限に達しました。",
  upload_rejected: "アップロードを確認できませんでした。もう一度お試しください。",
  paste_not_allowed: "領収書は貼り付けできません。ファイルを選んでください。",
  invalid_amount: "金額は1〜10,000,000円の整数で入力してください。",
  manual_not_allowed: "手入力は、読み取りに失敗したときだけできます。",
  invalid_reservation: "予約内容の入力を確認してください。",
  invalid_venue: "店の指定を確認してください。",
  no_extraction: "読み取り結果がありません。アップロードするか、手入力で確定してください。",
  no_transfer_to_approve: "承認できる振込がありません（すでに承認済みです）。",
  card_already_answered: "このカードは、すでに回答済みです。",
  action_rejected: "この操作は受け付けられませんでした。",
  retro_not_awaiting_organizer: "振り返りの集計が済んでから、確認できます。",
  memory_already_saved: "この振り返りは、すでに保存済みです。",
  memory_unavailable: "いま記憶に保存できませんでした。少し待って、もう一度お試しください。",
  memory_not_configured: "記憶の保存先が設定されていません。",
  not_configured: "サーバーの設定が済んでいません。",
  upstream_auth_failed: "サーバー間の認証に失敗しました。",
};

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 403) return "この操作を行う権限がありません。";
    if (e.status >= 500) return MESSAGES[e.code] ?? "うまく処理できませんでした。少し待って、もう一度お試しください。";
    return MESSAGES[e.code] ?? "操作を完了できませんでした。入力を確認してください。";
  }
  return "通信できませんでした。接続を確認してください。";
}

async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const user = getFirebaseAuth().currentUser;
  if (!user) throw new ApiError(401, "unauthenticated");
  const res = await fetch(`/api/dashboard/${path}`, {
    method,
    headers: { "X-Firebase-Token": await user.getIdToken(), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.json().then((j) => j?.detail, () => undefined);
    throw new ApiError(res.status, typeof detail === "string" ? detail : "error");
  }
  return (await res.json()) as T;
}

export const getMe = () => call<{ role: ApiRole }>("GET", "me");
export const listEvents = () => call<ApiEventSummary[]>("GET", "events");
export const getEvent = (id: string) => call<ApiEventDetail>("GET", `events/${id}`);

/** `eventId` が無ければ、最初の発言として planning のイベントが作られる */
export const sendMessage = (text: string, eventId?: string) =>
  call<{ event_id: string; reply: ApiMessage }>("POST", "messages", { event_id: eventId ?? null, text });

export const confirmPlan = (eventId: string, plan: ApiPlan) =>
  call<{ event_id: string; status: string }>("POST", `events/${eventId}/confirm-plan`, { plan });

export const selectVenue = (eventId: string, placeId: string, name: string) =>
  call("POST", `events/${eventId}/select-venue`, { place_id: placeId, name });

export const confirmExtraction = (
  eventId: string,
  kind: "reservation" | "receipt",
  values: Record<string, unknown>,
  source: "extracted" | "manual",
) => call("POST", `events/${eventId}/confirm-extraction`, { kind, values, source });

/** ファイルを署名付き URL に直接送り、登録する（種類・サイズの事前検査は補助。正は API） */
export async function uploadFile(eventId: string, kind: "reservation" | "receipt", file: File) {
  const issued = await call<{ upload_id: string; url: string }>("POST", `events/${eventId}/uploads`, {
    kind,
    content_type: file.type,
    size_bytes: file.size,
    source: "upload",
  });
  const put = await fetch(issued.url, { method: "PUT", headers: { "Content-Type": file.type }, body: file });
  if (!put.ok) throw new ApiError(502, "upload_rejected");
  return call("POST", `events/${eventId}/uploads/${issued.upload_id}/register`);
}

export const listNotifications = () => call<ApiNotification[]>("GET", "notifications");
export const markRead = (id: string) => call("POST", `notifications/${id}/read`);

export const confirmBudgetOverrun = (eventId: string) =>
  call("POST", `events/${eventId}/confirm-budget-overrun`);

export const markHeld = (eventId: string) => call("POST", `events/${eventId}/mark-held`);

/** 登場人物として、カードのボタンを押す（体験用のイベントだけ。値はサーバーのカードから取られる） */
export const pressPersonaCard = (eventId: string, cardId: string, index: number) =>
  call("POST", `events/${eventId}/persona-cards/${cardId}/actions`, { index });

/** 体験用の「銀行で承認する」（本物の銀行の振込には効かない） */
export const approveBank = (eventId: string, userId: string) =>
  call("POST", `events/${eventId}/bank-approvals`, { user_id: userId });

/** 振り返りの回答を、待たずに締め切る（その時点の回答で集計する） */
export const closeRetro = (eventId: string) => call("POST", `events/${eventId}/close-retro`);

/** 振り返りの確認。送るのは選択だけ（事実の文面は、サーバーが作り直す） */
export const confirmRetro = (
  eventId: string,
  body: { reuse_intent: "yes" | "no" | "unanswered"; include: string[]; decision: "save" | "skip" },
) => call<{ event_id: string; status: string }>("POST", `events/${eventId}/confirm-retro`, body);
