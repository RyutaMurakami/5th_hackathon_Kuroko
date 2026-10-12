"use client";

// 検証用の画面（/verify）。実 API（/api/dashboard/*）につないで、依頼 → 計画の確定 → 店 → 予約 → 領収書までを
// 通して確かめる。チャットは検証用で、最終的には Slack に統合する（SPEC 7.5）。
// 体験用（sandbox）のイベントでは、幹事・参加者・承認者の3人ぶんのチャットを並べ、参加者・承認者の
// カード（出欠と委任・按分の承認・銀行での承認）を、ここからも押せる（SPEC 7.7）。
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
import type { ApiEventDetail, ApiEventSummary, ApiPersona, ApiRole } from "@/lib/api-types";
import { useAuth } from "@/lib/auth";
import type { ChatMessage } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";
import { PersonaChat } from "./PersonaChat";
import { ScenarioHint } from "./ScenarioHint";
import { StepForms } from "./StepForms";
import { Avatar, Button, Caption, Card, ErrorBanner, InfoBanner, Pill } from "./ui";
import event from "./event.module.css";
import styles from "./verify.module.css";

const POLL_MS = 5000;

// 計画を確定するまでは、参加者がまだ決まっていない。列だけを先に見せる（名簿は kuroko-api が持つ）
const PLACEHOLDER_PERSONAS: ApiPersona[] = [
  { user_id: "kurao", display_name: "赤坂 くらお", job_title: "一般", cards: [] },
  { user_id: "hanako", display_name: "赤くら 花子", job_title: "部長", cards: [] },
];

function toChat(detail: ApiEventDetail): ChatMessage[] {
  return detail.messages.map((m) => ({
    messageId: m.message_id,
    role: m.role,
    text: m.text,
    createdAt: m.created_at,
  }));
}

export function VerifyView() {
  const { user } = useAuth();
  const [role, setRole] = useState<ApiRole | null>(null);
  const [events, setEvents] = useState<ApiEventSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApiEventDetail | null>(null);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

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
      const list = await listEvents();
      setEvents(list);
      if (id) setDetail(await getEvent(id));
    },
    [],
  );

  useEffect(() => {
    if (!user) return;
    void run(async () => {
      setRole((await getMe()).role);
      await refresh(selected);
    });
  }, [user, selected, refresh, run]);

  // Slack や銀行での操作で状態が進むので、一定の間隔で読み直す
  useEffect(() => {
    if (!user || !selected) return;
    const t = setInterval(() => void refresh(selected).catch(() => undefined), POLL_MS);
    return () => clearInterval(t);
  }, [user, selected, refresh]);

  // 登場人物の列。イベントを作る前・計画を確定する前は、空の列を出しておく（体験用のイベントだけ）
  const personas: ApiPersona[] = detail?.personas?.length ? detail.personas : PLACEHOLDER_PERSONAS;
  const showPersonas = role === "guest" && (!detail || detail.sandbox);
  const approverId = detail?.split?.approval.approver_user_id ?? "hanako";

  const send = async (text: string) => {
    setThinking(true);
    const ok = await run(async () => {
      const out = await sendMessage(text, selected ?? undefined);
      setSelected(out.event_id);
      await refresh(out.event_id);
    });
    if (ok) setDraft("");
    setThinking(false);
  };

  return (
    <main className={`${event.page} ${showPersonas ? styles.wide : ""}`}>
      <div className={event.pageHead}>
        <div>
          <h1 className={event.pageTitle}>動作の検証</h1>
          <p className={event.pageMeta}>
            実際の API につないで、依頼から領収書の確定まで通して確かめる画面です
            {role && `（${role === "guest" ? "ゲスト：体験用のイベント" : "幹事"}）`}
          </p>
        </div>
      </div>
      <InfoBanner>
        {showPersonas
          ? "あなたが幹事です。右の2列は、参加者（赤坂 くらお）と承認者（赤くら 花子）に届く KUROKO からのメッセージで、Slack に届くものと同じです。体験用に、ここからも2人の代わりにボタンを押せます。銀行は実験用の環境で、お金は仮想です。"
          : "委任・承認・振込は、この画面では行わず、Slack と銀行で行います（進行ヒントが案内します）。"}
      </InfoBanner>
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
            <Pill tone="navy">{e.status}</Pill>
          </button>
        ))}
      </div>

      {detail && <ScenarioHint hint={detail.hint} onUseChat={setDraft} />}

      {/* 幹事・参加者・承認者の3人ぶんの「KUROKO とのチャット」を並べる（SPEC 7.7） */}
      <div className={showPersonas ? styles.columns : undefined}>
        <section className={showPersonas ? styles.column : styles.main} aria-label="幹事と KUROKO のチャット">
          {showPersonas && (
            <header className={styles.columnHead}>
              <Avatar name="幹事" />
              <div className={styles.columnWho}>
                <span className={styles.columnName}>幹事（あなた）</span>
                <Caption>Web で依頼し、KUROKO の提案をそのつど確認して進めます</Caption>
              </div>
              {detail?.waiting_for?.where === "web" || !detail ? (
                <Pill tone="sun">あなたの番です</Pill>
              ) : (
                <Pill tone="navy">対応なし</Pill>
              )}
            </header>
          )}
          <Card title="KUROKO に依頼する" description="最初の発言で、計画中のイベントが作られます">
            <ChatPanel
              bare
              title=""
              messages={detail ? toChat(detail) : []}
              onSend={(t) => void send(t)}
              thinking={thinking}
              initialDraft={draft}
            />
          </Card>
          {detail && <StepForms detail={detail} onDone={() => refresh(detail.event_id)} run={run} />}
        </section>
        {showPersonas &&
          personas.map((p) => (
            <PersonaChat
              key={p.user_id}
              persona={p}
              role={p.user_id === approverId ? "承認者" : "参加者"}
              onPress={
                detail
                  ? (card, index) =>
                      run(async () => {
                        await pressPersonaCard(detail.event_id, card.card_id, index);
                        await refresh(detail.event_id);
                      })
                  : undefined
              }
              onApproveBank={
                detail && detail.bank_approval === "web"
                  ? () =>
                      run(async () => {
                        await approveBank(detail.event_id, p.user_id);
                        await refresh(detail.event_id);
                      }, "銀行で承認しました。1〜2分で、入金の確認に進みます。")
                  : undefined
              }
            />
          ))}
      </div>
    </main>
  );
}

