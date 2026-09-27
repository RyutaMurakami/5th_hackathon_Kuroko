"use client";

import { useState } from "react";
import { formatDateTime } from "@/lib/format";
import { RETRO_STATUS } from "@/lib/status";
import type { MemoryFact, Retrospective, RetroStatus } from "@/lib/types";
import { Button, Caption, Card, Chip, InfoBanner, Progress, StatBlock, StatusPill, uiStyles } from "./ui";
import styles from "./event.module.css";

const FACT_KIND_LABEL: Record<MemoryFact["kind"], string> = {
  venue_evaluation: "店の評価",
  budget_trend: "予算の傾向",
};

/**
 * 振り返りの集計と、KUROKOが次回に覚えること（DESIGN.md「Retro Summary Card」、SPEC 9.8）。
 * 個人ごとの回答は出さない。記憶の文面は編集できない（含める・含めないだけ）。
 */
export type RetroDecision = { decision: "saved" | "skipped"; includedIds: string[] };

export function RetroSummaryCard({
  retro,
  decided,
  onDecide,
}: {
  retro: Retrospective;
  /** この画面で決めた内容（段階が進んだあとも、選んだ事実だけを出す） */
  decided?: RetroDecision | null;
  onDecide?: (decision: RetroDecision) => void;
}) {
  const [status, setStatus] = useState<RetroStatus>(decided?.decision ?? retro.status);
  const [include, setInclude] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      retro.memoryFacts.map((f) => [f.factId, decided ? decided.includedIds.includes(f.factId) : f.include]),
    ),
  );
  const [savedAt, setSavedAt] = useState(retro.savedAt);
  const breakdown = retro.responseCount >= 3 && retro.likedCounts && retro.concernCounts;
  const savedFacts = retro.memoryFacts.filter((f) => include[f.factId]);

  return (
    <Card eyebrow="振り返り" title="振り返りと、KUROKOが覚えること" actions={<StatusPill view={RETRO_STATUS[status]} />}>
      <div className={styles.statsRow} style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
        <StatBlock label="回答" value={`${retro.responseCount} / ${retro.invitedCount}`} unit="名" />
        <StatBlock label="満足度" value={retro.avgRating !== null ? retro.avgRating.toFixed(1) : "—"} unit="/ 5" />
      </div>

      {breakdown ? (
        <div className={styles.bars}>
          <CountBars title="良かった点" items={retro.likedCounts ?? []} />
          <CountBars title="気になった点" items={retro.concernCounts ?? []} />
        </div>
      ) : (
        <div style={{ marginTop: "var(--spacing-16)" }}>
          <InfoBanner>回答が3件未満のため、内訳は表示していません（平均のみ）</InfoBanner>
        </div>
      )}

      {/* 記憶の確認は、awaiting_organizer のときだけ */}
      {status === "awaiting_organizer" && (
        <div className={styles.memory}>
          <p className={styles.memoryTitle}>次回に覚えさせる内容</p>
          <Caption>
            覚えさせた内容は、次回の企画で店選びの根拠として表示されます。お金の計算には使われません。個人名・個人ごとの回答は含まれません
          </Caption>
          <div style={{ marginTop: "var(--spacing-8)" }}>
            {retro.memoryFacts.map((fact) => (
              <label key={fact.factId} className={uiStyles.choice} style={{ borderBottom: "var(--border-width) solid var(--color-hairline)" }}>
                <input
                  type="checkbox"
                  checked={include[fact.factId]}
                  onChange={(e) => setInclude((prev) => ({ ...prev, [fact.factId]: e.target.checked }))}
                />
                <span className={styles.factText}>
                  <Chip>{FACT_KIND_LABEL[fact.kind]}</Chip>
                  <span>{fact.text}</span>
                </span>
              </label>
            ))}
          </div>
          <div className={styles.actions}>
            <Button
              onClick={() => {
                setSavedAt(new Date().toISOString());
                setStatus("saved");
                onDecide?.({ decision: "saved", includedIds: Object.keys(include).filter((id) => include[id]) });
              }}
            >
              次回に覚えさせる
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setStatus("skipped");
                onDecide?.({ decision: "skipped", includedIds: [] });
              }}
            >
              覚えさせない
            </Button>
          </div>
        </div>
      )}

      {status === "saved" && (
        <div className={styles.memory}>
          <p className={styles.memoryTitle}>このイベントで保存した記憶</p>
          <Caption>
            {savedFacts.length}件{savedAt ? `・${formatDateTime(savedAt)}` : ""}
          </Caption>
          <ul style={{ marginTop: "var(--spacing-8)" }}>
            {savedFacts.map((fact) => (
              <li key={fact.factId} className={styles.factRow}>
                <Chip>{FACT_KIND_LABEL[fact.kind]}</Chip>
                <span>{fact.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {status === "skipped" && (
        <div className={styles.memory}>
          <Caption>今回の振り返りは、記憶に保存しません。</Caption>
        </div>
      )}
    </Card>
  );
}

function CountBars({ title, items }: { title: string; items: { label: string; count: number }[] }) {
  const top = [...items].sort((a, b) => b.count - a.count).slice(0, 3);
  const max = Math.max(1, ...top.map((i) => i.count));
  return (
    <div>
      <span className={uiStyles.statLabel}>{title}</span>
      {top.map((item) => (
        <div key={item.label} className={styles.bar}>
          <span>{item.label}</span>
          <Progress value={item.count} max={max} label={`${item.label} ${item.count}件`} markDone={false} />
          <span className={styles.barCount}>{item.count}件</span>
        </div>
      ))}
    </div>
  );
}
