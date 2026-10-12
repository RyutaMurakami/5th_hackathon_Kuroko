"use client";

// KUROKO とのチャットの画面。幹事・参加者・承認者の3人ぶんのチャットを、最初から並べて出す（SPEC 7.7）。
// 画面は2つあり、作りは同じで、参加者・承認者の操作の場所だけが違う:
// - 体験用（/verify。審査員）: 2人の列のカードを、この画面から押せる。銀行は、承認ページを模した画面
// - 実演用（/demo。開発者）: 2人は Slack と本物の銀行（sunabar）で操作する。列は、届いたカードを映すだけ
// 幹事の入力（計画・店・予約・領収書・振り返り）は、チャットの流れの中のカードで完結する（SPEC 7.5）。
import { useCallback, useEffect, useState } from "react";
import {
  approveBank,
  errorText,
  getEvent,
  getMe,
  listEvents,
  pressPersonaCard,
  sendMessage,
} from "@/lib/api-client";
import type { ApiEventDetail, ApiEventSummary, ApiMe, ApiPersona, ApiUiMode } from "@/lib/api-types";
import { useAuth } from "@/lib/auth";
import type { ChatMessage } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";
import { PersonaChat } from "./PersonaChat";
import { ScenarioHint } from "./ScenarioHint";
import { StepForms } from "./StepForms";
import { Avatar, Button, Caption, ErrorBanner, InfoBanner, Pill } from "./ui";
import event from "./event.module.css";
import styles from "./verify.module.css";

const POLL_MS = 5000;

// 計画を確定するまでは、参加者がまだ決まっていない。列は最初から開いておく（名簿は kuroko-api が持つ）
const PLACEHOLDER_PERSONAS: ApiPersona[] = [
  { user_id: "kurao", display_name: "赤坂 くらお", job_title: "一般", cards: [] },
  { user_id: "hanako", display_name: "赤くら 花子", job_title: "部長", cards: [] },
];

const STATUS_LABEL: Record<string, string> = {
  planning: "計画", rsvp: "出欠", venue: "店", booked: "予約済み", day_of: "当日", receipt: "領収書",
  split: "按分", approval: "承認", payment: "振込", completed: "完了", retro: "振り返り", closed: "終了",
};

const COPY: Record<ApiUiMode, { title: string; meta: string; banner: string }> = {
  experience: {
    title: "KUROKO を体験する",
    meta: "幹事として依頼し、参加者・承認者の対応も、この画面で進められます",
    banner:
      "あなたが幹事です。右の2列は、参加者（赤坂 くらお）と承認者（赤くら 花子）に届く KUROKO からのメッセージで、Slack に届くものと同じです。体験用に、ここから2人の代わりにボタンを押せます。銀行の承認は、承認ページを模した画面で行い、お金は動きません。",
  },
  live: {
    title: "実演（開発者用）",
    meta: "参加者・承認者は Slack で操作し、振込は本物の銀行 API（sunabar）で実行します",
    banner:
      "開発者用の画面です。ここで作ったイベントは、赤坂 くらお・赤くら 花子の振込を、本物の銀行 API（sunabar。資金は仮想）に依頼します。2人は、Slack の DM と sunabar のサービスサイトで操作します。右の2列は、届いたカードを映すだけです。",
  },
};

function toChat(detail: ApiEventDetail): ChatMessage[] {
  return detail.messages.map((m) => ({
    messageId: m.message_id,
    role: m.role,
    text: m.text,
    createdAt: m.created_at,
  }));
}

export function VerifyView({ mode = "experience" }: { mode?: ApiUiMode }) {
  const { user } = useAuth();
  const [me, setMe] = useState<ApiMe | null>(null);
  const [events, setEvents] = useState<ApiEventSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApiEventDetail | null>(null);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const live = mode === "live";
  const copy = COPY[mode];

  const run = useCallback(async (fn: () => Promise<unknown>, done?: string) => {
    setError(null);
    setNotice(null);
    try {
      await fn();
      if (done) setNotice(done);
      return true;
    } catch (e) {
      setError(errorText(e));
      return false;
    }
  }, []);

  const refresh = useCallback(
    async (id: string | null) => {
      setEvents(await listEvents(mode));
      if (id) setDetail(await getEvent(id));
    },
    [mode],
  );

  useEffect(() => {
    if (!user) return;
    void run(async () => {
      setMe(await getMe());
      await refresh(selected);
    });
  }, [user, selected, refresh, run]);

  // 参加者・承認者の操作や、銀行の承認で状態が進むので、一定の間隔で読み直す
  useEffect(() => {
    if (!user || !selected) return;
    const t = setInterval(() => void refresh(selected).catch(() => undefined), POLL_MS);
    return () => clearInterval(t);
  }, [user, selected, refresh]);

  const blocked = live && me !== null && !me.live_allowed; // 実演用は、登録した開発者のアカウントだけ
  const personas: ApiPersona[] = detail?.personas?.length ? detail.personas : PLACEHOLDER_PERSONAS;
  const approverId = detail?.split?.approval.approver_user_id ?? "hanako";
  const hint = detail?.hint ?? me?.start_hints[mode] ?? null;
  const chats = hint?.example?.chats;
  const suggestions = Array.isArray(chats) ? chats.filter((c): c is string => typeof c === "string") : [];

  const send = async (text: string) => {
    setThinking(true);
    await run(async () => {
      const out = await sendMessage(text, selected ?? undefined, mode);
      setSelected(out.event_id);
      await refresh(out.event_id);
    });
    setThinking(false);
  };

  return (
    <main className={`${event.page} ${styles.wide}`}>
      <div className={event.pageHead}>
        <div>
          <h1 className={event.pageTitle}>{copy.title}</h1>
          <p className={event.pageMeta}>{copy.meta}</p>
        </div>
        <Pill tone={live ? "sun" : "navy"}>{live ? "実演用：本物の銀行 API" : "体験用：お金は動きません"}</Pill>
      </div>
      <InfoBanner>{copy.banner}</InfoBanner>
      {blocked && (
        <ErrorBanner>
          この画面は、登録した開発者のアカウントだけが使えます。体験するときは、上の「体験」を開いてください。
        </ErrorBanner>
      )}
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {notice && <InfoBanner>{notice}</InfoBanner>}

      <div className={styles.eventBar}>
        <Button
          variant="secondary"
          onClick={() => {
            setSelected(null);
            setDetail(null);
          }}
        >
          新しく依頼する
        </Button>
        {events.map((e) => (
          <button
            key={e.event_id}
            type="button"
            className={`${styles.eventButton} ${e.event_id === selected ? styles.eventButtonActive : ""}`}
            onClick={() => setSelected(e.event_id)}
          >
            <span className={styles.eventTitle}>{e.title || "（題名未定）"}</span>
            <Pill tone="navy">{STATUS_LABEL[e.status] ?? e.status}</Pill>
          </button>
        ))}
      </div>

      {/* 幹事・参加者・承認者の3人ぶんの「KUROKO とのチャット」。最初から、3つとも開いておく */}
      <div className={styles.columns}>
        <section className={styles.column} aria-label="幹事と KUROKO のチャット">
          <header className={styles.columnHead}>
            <Avatar name="幹事" />
            <div className={styles.columnWho}>
              <span className={styles.columnName}>幹事（あなた）</span>
              <Caption>依頼し、KUROKO の提案をそのつど確認して進めます</Caption>
            </div>
            {!detail || detail.waiting_for?.where === "web" || hint?.where === "web" ? (
              <Pill tone="sun">あなたの番です</Pill>
            ) : (
              <Pill tone="navy">対応なし</Pill>
            )}
          </header>
          {hint && <ScenarioHint hint={hint} />}
          <ChatPanel
            bare
            tall
            title=""
            messages={detail ? toChat(detail) : []}
            onSend={(t) => void send(t)}
            thinking={thinking}
            suggestions={blocked ? [] : suggestions}
            placeholder="第一開発チームの歓送迎会をやりたい"
            inlineKey={detail ? `${detail.status}:${detail.venue_candidates.length}:${detail.retro?.status ?? ""}` : ""}
            inline={
              detail ? <StepForms detail={detail} onDone={() => refresh(detail.event_id)} run={run} /> : undefined
            }
          />
        </section>
        {personas.map((p) => (
          <PersonaChat
            key={p.user_id}
            persona={p}
            role={p.user_id === approverId ? "承認者" : "参加者"}
            readOnly={live}
            onPress={
              detail && !live
                ? (card, index) =>
                    run(async () => {
                      await pressPersonaCard(detail.event_id, card.card_id, index);
                      await refresh(detail.event_id);
                    })
                : undefined
            }
            onApproveBank={
              detail && !live && detail.bank_approval === "web"
                ? () =>
                    run(async () => {
                      await approveBank(detail.event_id, p.user_id);
                      await refresh(detail.event_id);
                    }, "銀行で承認しました。1〜2分で、入金の確認に進みます。")
                : undefined
            }
            bankAmountYen={detail?.payments.find((pay) => pay.payer_user_id === p.user_id)?.amount_yen ?? null}
          />
        ))}
      </div>
    </main>
  );
}
