"use client";

import { AnimatePresence, motion } from "motion/react";
import { DURATION, EASE_OUT, SPRING } from "@/lib/motion";
import { FLOW_STEPS, flowStepIndex } from "@/lib/status";
import type { EventStatus } from "@/lib/types";
import { Icon } from "./Icon";
import styles from "./event.module.css";

/**
 * 飲み会の全体フローの中で、いまどこか（DESIGN.md「Flow Stepper」）。
 * 段階が進むと、線が次の円まで伸び、済んだ円はチェックに変わり、いまの円に輪が1回広がる。
 */
export function FlowStepper({ status, waitingOn }: { status: EventStatus; waitingOn: string | null }) {
  const current = flowStepIndex(status);
  // 終了は、振り返りの段階も済んだものとして扱う
  const finished = status === "closed";

  return (
    <ol className={styles.stepper}>
      {FLOW_STEPS.map((step, i) => {
        const done = i < current || (finished && i === current);
        const isCurrent = i === current && !finished;
        const className = [styles.step, done ? styles.stepDone : "", isCurrent ? styles.stepCurrent : ""].join(" ");
        return (
          <li key={step.label} className={className} aria-current={isCurrent ? "step" : undefined}>
            {i < FLOW_STEPS.length - 1 && (
              <span className={styles.stepLine} aria-hidden>
                <motion.span
                  className={styles.stepLineFill}
                  initial={false}
                  animate={{ scaleX: i < current ? 1 : 0, scaleY: i < current ? 1 : 0 }}
                  transition={{ duration: DURATION.slow, ease: EASE_OUT }}
                />
              </span>
            )}
            <span className={styles.stepDot}>
              {isCurrent && (
                <motion.span
                  key={status}
                  className={styles.stepPulse}
                  initial={{ opacity: 0.6, scale: 1 }}
                  animate={{ opacity: 0, scale: 1.8 }}
                  transition={{ duration: 0.9, ease: EASE_OUT }}
                  aria-hidden
                />
              )}
              <AnimatePresence mode="wait" initial={false}>
                {done ? (
                  <motion.span
                    key="check"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={SPRING}
                    style={{ display: "inline-flex" }}
                  >
                    <Icon name="check" size="sm" label="完了" />
                  </motion.span>
                ) : (
                  <motion.span key="num" exit={{ scale: 0 }} transition={{ duration: DURATION.fast }}>
                    {i + 1}
                  </motion.span>
                )}
              </AnimatePresence>
            </span>
            <div className={styles.stepBody}>
              <span className={styles.stepLabel}>{step.label}</span>
              <AnimatePresence mode="wait" initial={false}>
                {isCurrent && (
                  <motion.span
                    key={waitingOn ?? "progress"}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: DURATION.base, ease: EASE_OUT }}
                    className={waitingOn ? styles.waitChip : styles.progressNote}
                  >
                    {waitingOn ?? "進行中"}
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
