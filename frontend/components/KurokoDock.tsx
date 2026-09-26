"use client";

import { AnimatePresence, motion } from "motion/react";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { DURATION, SPRING } from "@/lib/motion";
import type { ActivityItem, ChatMessage } from "@/lib/types";
import { ActivityTimeline, activityKey } from "./ActivityTimeline";
import { ChatPanel } from "./ChatPanel";
import { Icon } from "./Icon";
import { Tabs, type TabItem } from "./Tabs";
import styles from "./detail.module.css";

type PanelTab = "chat" | "activity";

// ダミーの返事までの段取り（本番は send_message → 統括エージェントの応答をタイムラインで待つ）
const READ_MS = 900;
const REPLY_MS = 1600;
const DUMMY_REPLY = "承知しました。内容を整理しています。（ダミーの返答です。バックエンドにつなぐと、KUROKOが答えます）";

/**
 * KUROKO Launcher と KUROKO Panel（DESIGN.md「KUROKO Panel」）。
 * チャットとタイムラインを本文から外し、右から開くパネルに入れる。閉じている間の新着は件数のバッジで知らせる。
 */
export function KurokoDock({
  messages,
  activity,
  defaultOpen,
  onConfirmPlan,
}: {
  messages: ChatMessage[];
  activity: ActivityItem[];
  defaultOpen: boolean;
  onConfirmPlan?: () => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [tab, setTab] = useState<PanelTab>("chat");
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([]);
  const [localActivity, setLocalActivity] = useState<ActivityItem[]>([]);
  const [thinking, setThinking] = useState(false);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);
  const [freshKeys, setFreshKeys] = useState<Set<string>>(new Set());
  const seenMessages = useRef(new Set(messages.map((m) => m.messageId)));
  const seenActivity = useRef(new Set(activity.map(activityKey)));
  const launcherRef = useRef<HTMLButtonElement>(null);
  const openRef = useRef(open);
  const tabRef = useRef(tab);

  useEffect(() => {
    openRef.current = open;
    tabRef.current = tab;
  }, [open, tab]);

  // トーストの位置をパネルの左へずらすための印（detail.module.css）
  useEffect(() => {
    if (open) document.body.dataset.kurokoPanel = "open";
    else delete document.body.dataset.kurokoPanel;
    return () => {
      delete document.body.dataset.kurokoPanel;
    };
  }, [open]);

  const allMessages = [...messages, ...localMessages];
  const allActivity = [...localActivity, ...activity];

  // 段階が進んで KUROKO の発言が増えたら、開いていれば文字を流し、閉じていれば件数を足す
  useEffect(() => {
    const fresh = messages.filter((m) => !seenMessages.current.has(m.messageId));
    if (fresh.length === 0) return;
    fresh.forEach((m) => seenMessages.current.add(m.messageId));
    const lastKuroko = [...fresh].reverse().find((m) => m.role === "kuroko");
    if (openRef.current && tabRef.current === "chat" && lastKuroko) setStreamingId(lastKuroko.messageId);
    if (!openRef.current) setUnread((n) => n + fresh.length);
  }, [messages]);

  useEffect(() => {
    const fresh = activity.map(activityKey).filter((k) => !seenActivity.current.has(k));
    if (fresh.length === 0) return;
    fresh.forEach((k) => seenActivity.current.add(k));
    setFreshKeys(new Set(fresh));
    if (!openRef.current) setUnread((n) => n + fresh.length);
  }, [activity]);

  const close = useCallback(() => {
    setOpen(false);
    launcherRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  const send = (text: string) => {
    const now = () => new Date().toISOString();
    setLocalMessages((list) => [...list, { messageId: `local-${Date.now()}`, role: "organizer", text, createdAt: now() }]);
    setThinking(true);
    const reading: ActivityItem = { at: now(), text: "依頼を読み取っています", state: "progress" };
    setLocalActivity((list) => [reading, ...list]);
    setFreshKeys(new Set([activityKey(reading)]));

    setTimeout(() => {
      const checked: ActivityItem = { at: now(), text: "規程と過去の記憶を確認しました", state: "done" };
      setLocalActivity((list) => [
        checked,
        ...list.map((a) => (a === reading ? { ...a, text: "依頼を読み取りました", state: "done" as const } : a)),
      ]);
      setFreshKeys(new Set([activityKey(checked)]));
    }, READ_MS);

    setTimeout(() => {
      const id = `local-reply-${Date.now()}`;
      setThinking(false);
      setLocalMessages((list) => [...list, { messageId: id, role: "kuroko", text: DUMMY_REPLY, createdAt: now() }]);
      setStreamingId(id);
    }, REPLY_MS);
  };

  const current = allActivity[0];
  const tabs: TabItem<PanelTab>[] = [
    { value: "chat" as const, label: "チャット" },
    {
      value: "activity",
      label: "いましていること",
      dot: current?.state === "waiting" ? "sun" : current?.state === "progress" ? "navy" : undefined,
    },
  ];

  return (
    <>
      <motion.button
        ref={launcherRef}
        type="button"
        className={styles.launcher}
        onClick={() => {
          setOpen((v) => !v);
          setUnread(0);
        }}
        aria-expanded={open}
        aria-label={unread > 0 ? `KUROKO（新着 ${unread}件）` : "KUROKO"}
        whileHover={{ y: -2 }}
        whileTap={{ scale: 0.97 }}
      >
        <span className={styles.launcherIcon}>
          <Image src="/kuroko-icon.png" alt="" width={32} height={32} />
        </span>
        KUROKO
        <AnimatePresence>
          {unread > 0 && !open && (
            <motion.span
              key={unread}
              className={styles.launcherBadge}
              initial={{ scale: 0.4 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
              transition={SPRING}
              aria-hidden
            >
              {unread}
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              key="scrim"
              className={styles.scrim}
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.4 }}
              exit={{ opacity: 0 }}
              transition={{ duration: DURATION.base }}
              onClick={close}
              aria-hidden
            />
            <motion.aside
              key="panel"
              className={styles.panel}
              role="dialog"
              aria-label="KUROKO"
              initial={{ x: "100%", opacity: 0.6 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: "100%", opacity: 0.6 }}
              transition={SPRING}
            >
              <div className={styles.panelHead}>
                <p className={styles.panelTitle}>
                  <Icon name="chat" />
                  KUROKO
                </p>
                <button type="button" className={styles.iconButton} onClick={close} aria-label="閉じる">
                  <Icon name="close" />
                </button>
              </div>
              <div className={styles.panelTabs}>
                <Tabs items={tabs} value={tab} onChange={setTab} label="KUROKO" size="sm" idPrefix="kuroko" />
              </div>
              <div className={styles.panelBody} role="tabpanel" id="kuroko-panel">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={tab}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: DURATION.base }}
                  >
                    {tab === "chat" ? (
                      <ChatPanel
                        bare
                        autoFocus
                        messages={allMessages}
                        onSend={send}
                        thinking={thinking}
                        streamingId={streamingId}
                        onStreamDone={() => setStreamingId(null)}
                        onConfirmPlan={onConfirmPlan}
                      />
                    ) : (
                      <ActivityTimeline items={allActivity} freshKeys={freshKeys} />
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
