"use client";

import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { FADE_UP } from "@/lib/motion";
import type { Tone } from "@/lib/status";
import type { AppNotification } from "@/lib/types";
import { Icon } from "./Icon";
import { Pill } from "./ui";
import styles from "./detail.module.css";

// DESIGN.md「Toast」: 5秒で消える。同時に3件まで。同じ内容をベルにも1件足す
const LIFETIME_MS = 5000;
const MAX_TOASTS = 3;

const TONE_LABEL: Record<Tone, string> = {
  lagoon: "完了",
  sun: "Slack で対応待ち",
  navy: "進行",
  coral: "ブロック",
  slate: "記録",
};

export type ToastInput = { tone: Tone; text: string; eventId?: string; label?: string };
type ToastItem = ToastInput & { id: number };

type ToastContextValue = {
  toast: (input: ToastInput) => void;
  /** トーストと一緒にベルへ足した通知（このブラウザの中だけ） */
  extraNotifications: AppNotification[];
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast は ToastProvider の中で使う");
  return ctx;
}

const KIND_BY_TONE = {
  lagoon: "completed",
  sun: "waiting_on_human",
  navy: "confirm_needed",
  coral: "blocked",
  slate: "completed",
} as const;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [extra, setExtra] = useState<AppNotification[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((list) => list.filter((t) => t.id !== id)), []);

  const toast = useCallback((input: ToastInput) => {
    const id = nextId.current++;
    setToasts((list) => [...list, { ...input, id }].slice(-MAX_TOASTS));
    if (input.eventId) {
      setExtra((list) => [
        {
          notificationId: `local-${id}`,
          eventId: input.eventId as string,
          kind: KIND_BY_TONE[input.tone],
          text: input.text,
          createdAt: new Date().toISOString(),
          read: false,
        },
        ...list,
      ]);
    }
  }, []);

  const value = useMemo(() => ({ toast, extraNotifications: extra }), [toast, extra]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className={styles.toastViewport}>
        <AnimatePresence initial={false}>
          {toasts.map((t) => (
            <ToastCard key={t.id} item={t} onDismiss={dismiss} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const [paused, setPaused] = useState(false);

  // 他のトーストが増えても、自分のタイマーは最初からにしない（onDismiss は id を受け取る安定した関数）
  useEffect(() => {
    if (paused) return;
    const timer = setTimeout(() => onDismiss(item.id), LIFETIME_MS);
    return () => clearTimeout(timer);
  }, [paused, onDismiss, item.id]);

  return (
    <motion.div
      layout
      className={styles.toast}
      role={item.tone === "coral" ? "alert" : "status"}
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 24, transition: { duration: 0.15 } }}
      transition={FADE_UP}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className={styles.toastBody}>
        <Pill tone={item.tone}>{item.label ?? TONE_LABEL[item.tone]}</Pill>
        <p className={styles.toastText}>{item.text}</p>
      </div>
      <button type="button" className={styles.iconButton} onClick={() => onDismiss(item.id)} aria-label="通知を閉じる">
        <Icon name="close" size="sm" />
      </button>
    </motion.div>
  );
}
