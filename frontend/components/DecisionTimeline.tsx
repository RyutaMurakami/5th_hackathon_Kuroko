"use client";

import { formatDateTime } from "@/lib/format";
import { ACTION_TYPE_TONE } from "@/lib/status";
import type { DecisionLogEntry } from "@/lib/types";
import { Card, EmptyState, Pill } from "./ui";
import styles from "./event.module.css";

const ACTOR_LABEL: Record<DecisionLogEntry["actor"], string> = {
  kuroko: "KUROKO",
  payment_agent: "支払いエージェント",
  human: "人",
};

const TONE_DOT = { navy: "progress", sun: "waiting", lagoon: "done", coral: "blocked", slate: "slate" } as const;

/** 経緯（判断ログ）。イベント詳細の「経緯」タブに出す（DESIGN.md「Decision Timeline」） */
export function DecisionTimeline({ entries }: { entries: DecisionLogEntry[] }) {
  return (
    <Card eyebrow="経緯" title="何を・なぜ行ったか" description={`KUROKOと人の判断の記録（${entries.length}件）。新しい順`}>
      {entries.length === 0 ? (
        <EmptyState title="まだ記録はありません">KUROKOが判断すると、ここに理由と規程が残ります。</EmptyState>
      ) : (
        <ol className={styles.timeline}>
          {entries.map((entry, i) => {
            const tone = ACTION_TYPE_TONE[entry.actionType];
            const className = [
              styles.tlItem,
              tone === "coral" ? styles.tlBlocked : "",
              tone === "sun" ? styles.tlWaiting : "",
            ].join(" ");
            return (
              <li key={`${entry.at}-${i}`} className={className}>
                <span className={`${styles.tlDot} ${styles[`dot-${TONE_DOT[tone]}`]}`} aria-hidden />
                <div>
                  <div className={styles.tlHead}>
                    <span className={styles.tlTime}>{formatDateTime(entry.at)}</span>
                    <span className={styles.actor}>{ACTOR_LABEL[entry.actor]}</span>
                    <Pill tone={tone}>{entry.actionType}</Pill>
                  </div>
                  <p className={styles.tlText}>{entry.summary}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
