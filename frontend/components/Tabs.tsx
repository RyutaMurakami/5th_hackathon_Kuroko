"use client";

import { motion } from "motion/react";
import { useId, useRef } from "react";
import { SPRING } from "@/lib/motion";
import type { Tone } from "@/lib/status";
import styles from "./detail.module.css";

export type TabItem<T extends string> = {
  value: T;
  label: string;
  /** タブの右に添える小さな補足（例: 「5/7」） */
  meta?: string;
  /** 状態のドット（待ち＝sun など） */
  dot?: Tone;
};

/**
 * Tab Pill Navigation（DESIGN.md）。選択中の塗りは、選び直すと次のタブへ滑って移る。
 * キーボードは ←→ で移動する。
 */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
  size = "md",
  idPrefix,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  size?: "sm" | "md";
  idPrefix?: string;
}) {
  const autoId = useId();
  const prefix = idPrefix ?? autoId;
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const next = (index + (e.key === "ArrowRight" ? 1 : -1) + items.length) % items.length;
    refs.current[next]?.focus();
    onChange(items[next].value);
  };

  return (
    <div className={`${styles.tabs} ${size === "sm" ? styles.tabsSm : ""}`} role="tablist" aria-label={label}>
      {items.map((item, i) => {
        const selected = item.value === value;
        return (
          <button
            key={item.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`${prefix}-tab-${item.value}`}
            aria-selected={selected}
            aria-controls={`${prefix}-panel`}
            tabIndex={selected ? 0 : -1}
            className={`${styles.tab} ${selected ? styles.tabSelected : ""}`}
            onClick={() => onChange(item.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
          >
            {selected && (
              <motion.span layoutId={`${prefix}-indicator`} className={styles.tabIndicator} transition={SPRING} />
            )}
            <span className={styles.tabLabel}>
              {item.label}
              {item.dot && <span className={`${styles.tabDot} ${styles[`tabDot-${item.dot}`]}`} aria-hidden />}
              {item.meta && <span className={styles.tabMeta}>{item.meta}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
