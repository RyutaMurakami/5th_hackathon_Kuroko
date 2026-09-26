"use client";

import { useState } from "react";
import { formatNumber } from "@/lib/format";
import type { VenueCandidate } from "@/lib/types";
import { Button, Caption, Card, Chip, Pill, uiStyles } from "./ui";
import styles from "./event.module.css";

/**
 * 店舗候補の選択（DESIGN.md「Venue Choice Card」）。
 * 記憶に基づく理由は表示だけ。金額・帰りやすさの数字は記憶によって変えない。
 */
export function VenueChoiceCard({
  candidates,
  onSelected,
}: {
  candidates: VenueCandidate[];
  onSelected: (candidate: VenueCandidate) => void;
}) {
  const [selectedId, setSelectedId] = useState(candidates[0]?.candidateId ?? "");
  const [decided, setDecided] = useState<VenueCandidate | null>(null);

  return (
    <Card
      eyebrow="店舗候補"
      title={decided ? `「${decided.name}」で進めます` : "お店を1つ選んでください"}
      description="全員の最寄り駅から帰りやすい順。予約は幹事がお店で行い、予約画面をこの画面にアップロードします"
      actions={decided ? <Pill tone="lagoon">選択済み</Pill> : undefined}
    >
      <fieldset style={{ border: 0, margin: 0, padding: 0 }} disabled={!!decided}>
        <legend className="visually-hidden">店舗候補</legend>
        <div className={styles.venueList}>
          {candidates.map((c) => {
            const selected = c.candidateId === selectedId;
            return (
              <div key={c.candidateId} className={`${styles.venue} ${selected ? styles.venueSelected : ""}`}>
                <label className={`${styles.venueLabel} ${uiStyles.choice}`}>
                  <input
                    type="radio"
                    name="venue"
                    value={c.candidateId}
                    checked={selected}
                    onChange={() => setSelectedId(c.candidateId)}
                  />
                  <span className={styles.venueBody}>
                    <span className={styles.venueName}>{c.name}</span>
                    <span className={styles.venueMeta}>
                      <span>
                        1人 {formatNumber(c.pricePerPersonMin)}〜{formatNumber(c.pricePerPersonMax)}円
                      </span>
                      <span>
                        帰りやすさ 最大 {c.maxTravelMinutes}分・平均 {c.avgTravelMinutes}分
                      </span>
                      <span>{c.area}</span>
                    </span>
                    <span className={styles.chips}>
                      {c.features.map((f) => (
                        <Chip key={f} tone="subtle">
                          {f}
                        </Chip>
                      ))}
                    </span>
                  </span>
                </label>
                {/* 理由がないときは何も出さない（空の帯を作らない） */}
                {c.memoryNote && (
                  <div className={styles.memoryBand}>
                    <Chip>記憶</Chip>
                    <span className={styles.memoryBandText}>{c.memoryNote}</span>
                    {c.memoryPeriod && <Caption>{c.memoryPeriod}</Caption>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </fieldset>
      {!decided && (
        <div className={styles.actions}>
          <Button
            onClick={() => {
              const candidate = candidates.find((c) => c.candidateId === selectedId);
              if (!candidate) return;
              setDecided(candidate);
              onSelected(candidate);
            }}
          >
            この店で進める
          </Button>
        </div>
      )}
    </Card>
  );
}
