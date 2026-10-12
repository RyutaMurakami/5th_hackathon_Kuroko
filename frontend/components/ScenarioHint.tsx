"use client";

import type { ApiHint } from "@/lib/api-types";
import { Pill } from "./ui";
import styles from "./verify.module.css";

const WHERE: Record<ApiHint["where"], { label: string; tone: "navy" | "sun" | "lagoon" }> = {
  web: { label: "この画面で", tone: "navy" },
  slack: { label: "Slack で", tone: "sun" },
  bank: { label: "銀行（sunabar）で", tone: "sun" },
  system: { label: "KUROKO が自動で", tone: "lagoon" },
};

/**
 * シナリオの進行ヒント（SPEC 7.5）。チャットの列の先頭に、**いつも**出す。
 * いまの段階で次に何を・どこで・誰がするかを示す。案内だけで、操作の代行ではない。
 * チャットの入力の候補は、入力欄のすぐ上に出す（ChatPanel の `suggestions`）。
 */
export function ScenarioHint({ hint, compact = false }: { hint: ApiHint; compact?: boolean }) {
  const where = WHERE[hint.where];
  return (
    // compact: チャットの列の中（見出しのすぐ下）に、帯として出す
    <aside className={`${styles.hint} ${compact ? styles.hintCompact : ""}`} aria-label="次にすること">
      <div className={styles.hintHead}>
        <span className={styles.hintStep}>
          次にすること（{hint.step} / {hint.total}）
        </span>
        <span>{hint.title}</span>
        <Pill tone={where.tone}>
          {where.label}・{hint.who}
        </Pill>
      </div>
      <div
        className={styles.hintBar}
        role="progressbar"
        aria-label="シナリオの進み具合"
        aria-valuemin={1}
        aria-valuemax={hint.total}
        aria-valuenow={hint.step}
      >
        <span className={styles.hintFill} style={{ width: `${(hint.step / hint.total) * 100}%` }} />
      </div>
      <p className={styles.hintText}>{hint.do}</p>
    </aside>
  );
}
