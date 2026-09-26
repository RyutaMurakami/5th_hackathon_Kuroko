"use client";

import { AnimatePresence, motion } from "motion/react";
import { formatDateTime, formatNumber } from "@/lib/format";
import { DURATION, EASE_OUT, FADE_UP } from "@/lib/motion";
import { CONSENT_STATE, EVENT_STATUS, FLOW_STEPS, flowStepIndex } from "@/lib/status";
import type { EventDetail } from "@/lib/types";
import { AgentStatus } from "./AgentStatus";
import { AnimatedNumber } from "./AnimatedNumber";
import { FlowStepper } from "./FlowStepper";
import { Icon } from "./Icon";
import { SlackHandoffCard } from "./SlackHandoffCard";
import { Avatar, Caption, HighlightCard, OutlinePill, Pill, RoleBadge, StatusPill } from "./ui";
import styles from "./detail.module.css";

/**
 * イベント詳細の概要（DESIGN.md「Event Summary」）。
 * ①誰が幹事か ②全体フローのどこか ③次に誰を待っているか だけを1枚で伝え、詳しい表はタブへ回す。
 */
export function EventSummary({
  event,
  onJump,
}: {
  event: EventDetail;
  /** 小さな数字を押したら、送金・承諾のタブへ移る */
  onJump: () => void;
}) {
  const approver = event.participants.find((p) => p.role === "approver");
  const honorees = event.participants.filter((p) => p.role === "guest_of_honor");
  const waitingCount = event.participants.filter((p) => CONSENT_STATE[p.consent].tone === "sun").length;
  const stepLabel = FLOW_STEPS[flowStepIndex(event.status)].label;
  const sub = [
    approver ? `承認者: ${approver.displayName}` : "承認者: 出欠の確定後に決まります",
    honorees.length > 0 ? `主役: ${honorees.map((p) => p.displayName).join("・")}` : null,
  ]
    .filter(Boolean)
    .join(" ／ ");

  return (
    <HighlightCard>
      <div className={styles.summary}>
        <div className={styles.summaryHead}>
          <div>
            <h1 className={styles.summaryTitle}>{event.title}</h1>
            <p className={styles.summaryMeta}>
              <span>{formatDateTime(event.datetime)}</span>
              {event.venueName && <span>{event.venueName}</span>}
              <span>{event.companyName}</span>
              {event.sandbox && <OutlinePill>体験用（7日で削除）</OutlinePill>}
            </p>
          </div>
          <StatusPill view={EVENT_STATUS[event.status]} />
        </div>

        <div className={styles.organizerRow}>
          <Avatar name={event.organizerName} />
          <div>
            <p className={styles.organizerName}>
              {event.organizerName}
              <RoleBadge role="organizer" />
            </p>
            <Caption>{sub}</Caption>
          </div>
        </div>

        <hr className={styles.divider} />

        <div>
          <AnimatePresence mode="wait" initial={false}>
            <motion.p
              key={event.status === "closed" ? "closed" : stepLabel}
              className={styles.stageTitle}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: DURATION.base, ease: EASE_OUT }}
            >
              {event.status === "closed" ? "すべての段階が終わりました" : `いまは「${stepLabel}」の段階です`}
            </motion.p>
          </AnimatePresence>
          <FlowStepper status={event.status} waitingOn={event.waitingOn} />
        </div>

        <AgentStatus workers={event.workers} />

        <AnimatePresence mode="wait" initial={false}>
          {event.handoff ? (
            <motion.div
              key={`handoff-${event.status}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={FADE_UP}
            >
              <SlackHandoffCard handoff={event.handoff} />
            </motion.div>
          ) : (
            <motion.p
              key={`next-${event.status}`}
              className={styles.nextStep}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={FADE_UP}
            >
              <Icon name="info" size="sm" />
              {event.nextStep}
            </motion.p>
          )}
        </AnimatePresence>

        <div className={styles.miniStats}>
          <button type="button" className={styles.miniStat} onClick={onJump}>
            <span className={styles.miniStatLabel}>承諾</span>
            <span className={styles.miniStatValue}>
              {event.consentTargetCount > 0 ? (
                <>
                  <AnimatedNumber value={event.consentedCount} /> / {event.consentTargetCount}
                </>
              ) : (
                "—"
              )}
              <span className={styles.miniStatUnit}>名</span>
            </span>
          </button>
          <button type="button" className={styles.miniStat} onClick={onJump}>
            <span className={styles.miniStatLabel}>送金済み</span>
            <span className={styles.miniStatValue}>
              {event.billedYen > 0 ? (
                <>
                  <AnimatedNumber value={event.paidYen} /> / {formatNumber(event.billedYen)}
                </>
              ) : (
                "—"
              )}
              <span className={styles.miniStatUnit}>円</span>
            </span>
          </button>
          <button type="button" className={styles.miniStat} onClick={onJump}>
            <span className={styles.miniStatLabel}>
              人の対応待ち
              {waitingCount > 0 && <Pill tone="sun">対応待ち</Pill>}
            </span>
            <span className={styles.miniStatValue}>
              <AnimatedNumber value={waitingCount} />
              <span className={styles.miniStatUnit}>名</span>
            </span>
          </button>
        </div>
      </div>
    </HighlightCard>
  );
}
