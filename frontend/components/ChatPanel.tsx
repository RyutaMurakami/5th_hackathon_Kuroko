"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import { formatTime } from "@/lib/format";
import { FADE_UP, STREAM_CHARS_PER_SEC } from "@/lib/motion";
import type { ChatMessage, EventPlanProposal } from "@/lib/types";
import { Button, Caption, Card, Eyebrow, Pill } from "./ui";
import styles from "./event.module.css";

const PLACEHOLDER = "来週金曜、チーム8人で軽く飲みに行きたい";

/**
 * 依頼と対話（DESIGN.md「Chat Panel」、SPEC 7.5）。表示だけを持ち、状態は呼び出し側（KUROKO Panel）が持つ。
 * KUROKOの返事は「考えています…」のあと文字が順に流れる。提案はボタンで確認する（チャットの中の確認カード）。
 */
export function ChatPanel({
  messages,
  onSend,
  thinking = false,
  streamingId = null,
  onStreamDone,
  onConfirmPlan,
  bare = false,
  title = "KUROKOに依頼する",
  autoFocus = false,
}: {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  thinking?: boolean;
  /** いま文字を流している KUROKO の発言 */
  streamingId?: string | null;
  onStreamDone?: () => void;
  onConfirmPlan?: () => void;
  /** KUROKO Panel の中ではカードの枠を付けない */
  bare?: boolean;
  title?: string;
  autoFocus?: boolean;
}) {
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inputId = useId();

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, thinking, streamingId]);

  const send = () => {
    const text = draft.trim();
    if (!text || thinking || streamingId) return;
    onSend(text);
    setDraft("");
  };

  const body = (
    <div className={styles.chat}>
      {messages.length > 0 && (
        <div className={styles.messages} ref={listRef} aria-live="polite">
          <AnimatePresence initial={false}>
            {messages.map((m) => (
              <MessageBubble
                key={m.messageId}
                message={m}
                streaming={m.messageId === streamingId}
                onStreamDone={onStreamDone}
                onConfirmPlan={onConfirmPlan}
              />
            ))}
            {thinking && (
              <motion.div
                key="thinking"
                className={styles.thinking}
                role="status"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={FADE_UP}
              >
                <span className={styles.thinkingDots} aria-hidden>
                  <span />
                  <span />
                  <span />
                </span>
                KUROKOが考えています…
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
      <div className={styles.composer}>
        <label htmlFor={inputId} className="visually-hidden">
          依頼の内容
        </label>
        <textarea
          id={inputId}
          ref={inputRef}
          className={styles.textarea}
          value={draft}
          placeholder={`例: ${PLACEHOLDER}`}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            // Enter は改行、Ctrl/⌘+Enter で送信
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              send();
            }
          }}
        />
        <div className={styles.composerRow}>
          <Caption>Ctrl / ⌘ + Enter で送信</Caption>
          <Button onClick={send} disabled={thinking || !!streamingId}>
            送る
          </Button>
        </div>
      </div>
    </div>
  );

  if (bare) return body;
  return (
    <Card eyebrow="チャット" title={title}>
      {body}
    </Card>
  );
}

function MessageBubble({
  message,
  streaming,
  onStreamDone,
  onConfirmPlan,
}: {
  message: ChatMessage;
  streaming: boolean;
  onStreamDone?: () => void;
  onConfirmPlan?: () => void;
}) {
  const fromOrganizer = message.role === "organizer";
  return (
    <>
      <motion.div
        className={`${styles.message} ${fromOrganizer ? styles.fromOrganizer : styles.fromKuroko}`}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={FADE_UP}
        layout="position"
      >
        <span className="visually-hidden">{fromOrganizer ? "幹事" : "KUROKO"}：</span>
        {streaming ? <StreamingText text={message.text} onDone={onStreamDone} /> : message.text}
        <span className={styles.messageMeta}>
          {fromOrganizer ? "幹事" : "KUROKO"}・{formatTime(message.createdAt)}
        </span>
      </motion.div>
      {message.proposal && !streaming && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={FADE_UP}>
          <ProposalCard proposal={message.proposal} onConfirm={onConfirmPlan} />
        </motion.div>
      )}
    </>
  );
}

/** 文字を順に出す。流れ終わるまで読み上げは待つ（途中は aria-hidden）。視差効果を減らす設定では一度に出す */
function StreamingText({ text, onDone }: { text: string; onDone?: () => void }) {
  const reduce = useReducedMotion();
  const [count, setCount] = useState(reduce ? text.length : 0);
  const doneRef = useRef(onDone);
  useEffect(() => {
    doneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (reduce) {
      doneRef.current?.();
      return;
    }
    const started = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const next = Math.min(text.length, Math.floor(((now - started) / 1000) * STREAM_CHARS_PER_SEC));
      setCount(next);
      if (next < text.length) frame = requestAnimationFrame(tick);
      else doneRef.current?.();
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [text, reduce]);

  const finished = count >= text.length;
  return (
    <>
      <span aria-hidden={!finished}>{text.slice(0, count)}</span>
      {!finished && <span className={styles.caret} aria-hidden />}
    </>
  );
}

function ProposalCard({ proposal, onConfirm }: { proposal: EventPlanProposal; onConfirm?: () => void }) {
  return (
    <div className={styles.proposal}>
      <div className={styles.collapse}>
        <Eyebrow>イベントの計画の確認</Eyebrow>
        {proposal.confirmedAt && <Pill tone="lagoon">確定済み（幹事・{formatTime(proposal.confirmedAt)}）</Pill>}
      </div>
      <dl className={styles.proposalList}>
        {proposal.items.map((item) => (
          <div key={item.label} style={{ display: "contents" }}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
      {!proposal.confirmedAt && onConfirm && (
        <>
          <Caption className={styles.cellNote}>
            進めると、Slack で参加者に出欠と支払いの委任の依頼が届きます。委任は各自が Slack で行います
          </Caption>
          <div className={styles.actions}>
            <Button onClick={onConfirm}>この内容で進める</Button>
          </div>
        </>
      )}
    </div>
  );
}
