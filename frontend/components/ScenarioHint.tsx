"use client";

import type { ApiHint } from "@/lib/api-types";
import { Button, Card, Pill } from "./ui";
import styles from "./verify.module.css";

const WHERE: Record<ApiHint["where"], { label: string; tone: "navy" | "sun" | "lagoon" }> = {
  web: { label: "この画面で", tone: "navy" },
  slack: { label: "Slack で", tone: "sun" },
  bank: { label: "銀行（sunabar）で", tone: "sun" },
  system: { label: "KUROKO が自動で", tone: "lagoon" },
};

/**
 * シナリオの進行ヒント（SPEC 7.5）。いまの段階で次に何を・どこで・誰がするかと、入力例を示す。
 * 案内だけで、操作の代行ではない（Slack・銀行で人が行う操作は、そこで行うことを示すだけ）。
 */
export function ScenarioHint({
  hint,
  onUseChat,
}: {
  hint: ApiHint;
  /** チャットの入力例を、入力欄に入れる */
  onUseChat?: (text: string) => void;
}) {
  const where = WHERE[hint.where];
  const chat = typeof hint.example?.chat === "string" ? hint.example.chat : null;
  return (
    <Card
      eyebrow={`シナリオの進行 ${hint.step} / ${hint.total}`}
      title={hint.title}
      description={hint.do}
      actions={
        <Pill tone={where.tone}>
          {where.label}・{hint.who}
        </Pill>
      }
    >
      <div className={styles.hintBar} role="progressbar" aria-valuemin={1} aria-valuemax={hint.total} aria-valuenow={hint.step}>
        <span className={styles.hintFill} style={{ width: `${(hint.step / hint.total) * 100}%` }} />
      </div>
      {chat && (
        <div className={styles.example}>
          <span className={styles.exampleLabel}>入力例</span>
          <span className={styles.exampleText}>{chat}</span>
          {onUseChat && (
            <Button variant="secondary" onClick={() => onUseChat(chat)}>
              入力欄に入れる
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}
