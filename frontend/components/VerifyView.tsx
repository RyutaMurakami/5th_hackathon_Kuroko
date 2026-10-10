"use client";

// 検証用の画面（/verify）。実 API（/api/dashboard/*）につないで、依頼 → 計画の確定 → 店 → 予約 → 領収書までを
// 通して確かめる。チャットは検証用で、最終的には Slack に統合する（SPEC 7.5）。
// 委任・承認・振込の操作は置かない（Slack・銀行で行う。進行ヒントが案内する）。
import { useCallback, useEffect, useState } from "react";
import {
  errorText,
  getEvent,
  getMe,
  listEvents,
  sendMessage,
} from "@/lib/api-client";
import type { ApiEventDetail, ApiEventSummary, ApiRole } from "@/lib/api-types";
import { useAuth } from "@/lib/auth";
import type { ChatMessage } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";
import { ScenarioHint } from "./ScenarioHint";
import { StepForms } from "./StepForms";
import { Button, Card, ErrorBanner, InfoBanner, Pill } from "./ui";
import event from "./event.module.css";
import styles from "./verify.module.css";

const POLL_MS = 5000;

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
    <main className={event.page}>
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
        チャットは検証用です。最終的な依頼や回答は Slack で行います。委任・承認・振込は、この画面では行わず、
        Slack と銀行で行います（進行ヒントが案内します）。
      </InfoBanner>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {notice && <InfoBanner>{notice}</InfoBanner>}

      <div className={styles.layout}>
        <aside className={styles.side}>
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
        </aside>

        <div className={styles.main}>
          {detail && <ScenarioHint hint={detail.hint} onUseChat={setDraft} />}
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
          {detail && (
            <StepForms
              detail={detail}
              onDone={() => refresh(detail.event_id)}
              run={run}
            />
          )}
        </div>
      </div>
    </main>
  );
}

