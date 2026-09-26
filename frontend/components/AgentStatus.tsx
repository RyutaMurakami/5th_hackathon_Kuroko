"use client";

import { AnimatePresence, motion } from "motion/react";
import { DURATION, EASE_OUT } from "@/lib/motion";
import type { Worker } from "@/lib/types";
import { Eyebrow } from "./ui";
import styles from "./detail.module.css";

const STATE_LABEL: Record<Worker["state"], string> = {
  running: "動いています",
  waiting: "待っています",
  done: "済みました",
};

/**
 * いま動いているもの（DESIGN.md「Agent Status」）。
 * エージェント（LLM を使う）と、エージェントではない仕組み（コード・RAG Engine・Memory Bank）を、印で区別する。
 */
export function AgentStatus({ workers }: { workers: Worker[] }) {
  if (workers.length === 0) return null;
  return (
    <div>
      <Eyebrow>いま動いているもの</Eyebrow>
      <ul className={styles.workers} aria-live="polite">
        <AnimatePresence mode="popLayout" initial={false}>
          {workers.map((w) => (
            <motion.li
              key={w.id}
              layout="position"
              className={styles.worker}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: DURATION.base, ease: EASE_OUT }}
            >
              <span className={`${styles.workerDot} ${styles[`workerDot-${w.state}`]}`} aria-hidden />
              <span className={w.kind === "agent" ? styles.kindAgent : styles.kindSystem}>
                {w.kind === "agent" ? "Agent" : "コード"}
              </span>
              <div className={styles.workerBody}>
                <p className={styles.workerText}>
                  <strong>{w.name}</strong>が、{w.action}
                  <span className="visually-hidden">（{STATE_LABEL[w.state]}）</span>
                </p>
                <span className={styles.workerRole}>{w.role}</span>
              </div>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  );
}
