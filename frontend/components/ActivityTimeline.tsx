"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { formatShortDateTime } from "@/lib/format";
import { FADE_UP } from "@/lib/motion";
import type { ActivityItem } from "@/lib/types";
import { EmptyState, OutlinePill, TextButton } from "./ui";
import styles from "./event.module.css";

// 長くなりすぎないよう、最初は新しいものから数件だけ出す
const INITIAL_COUNT = 6;

const STATE_LABEL: Record<ActivityItem["state"], string> = {
  progress: "進行中",
  waiting: "待ち",
  done: "完了",
  blocked: "ブロック",
};

export function activityKey(item: ActivityItem): string {
  return `${item.at}|${item.text}`;
}

/**
 * KUROKOがいましていること（DESIGN.md「Activity Timeline」）。新しい順で、先頭がいまの項目。
 * 新しい項目は上から滑って入り、少し光ってから通常の背景に戻る。KUROKO Panel の中で使う。
 */
export function ActivityTimeline({ items, freshKeys }: { items: ActivityItem[]; freshKeys?: Set<string> }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? items : items.slice(0, INITIAL_COUNT);

  if (items.length === 0) {
    return <EmptyState title="まだ動いていません">依頼を送ると、KUROKOの作業がここに並びます。</EmptyState>;
  }

  return (
    <div>
      <ol className={styles.timeline} aria-live="polite">
        <AnimatePresence initial={false}>
          {visible.map((item, i) => {
            const key = activityKey(item);
            const current = i === 0 && item.state !== "done";
            const className = [
              styles.tlItem,
              current && item.state === "waiting" ? styles.tlWaiting : "",
              current && item.state === "progress" ? styles.tlCurrent : "",
              !current && freshKeys?.has(key) ? styles.tlFresh : "",
              item.state === "blocked" ? styles.tlBlocked : "",
            ].join(" ");
            return (
              <motion.li
                key={key}
                layout="position"
                className={className}
                initial={{ opacity: 0, y: -12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={FADE_UP}
              >
                <span className={`${styles.tlDot} ${styles[`dot-${item.state}`]}`} aria-hidden />
                <div>
                  <span className={styles.tlTime}>{formatShortDateTime(item.at)}</span>
                  <span className="visually-hidden">（{STATE_LABEL[item.state]}）</span>
                  <p className={styles.tlText}>{item.text}</p>
                  {item.proxy && (
                    <span className={styles.tlProxy}>
                      <OutlinePill>デモ用の代行</OutlinePill>
                    </span>
                  )}
                </div>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ol>
      {items.length > INITIAL_COUNT && (
        <div style={{ marginTop: "var(--spacing-8)" }}>
          <TextButton onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
            {showAll ? "新しいものだけ表示" : `すべて表示（${items.length}件）`}
          </TextButton>
        </div>
      )}
    </div>
  );
}
