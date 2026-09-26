"use client";

import Link from "next/link";
import { useDemoHref } from "@/lib/demo";
import { formatDateTime, formatYen } from "@/lib/format";
import { EVENT_STATUS } from "@/lib/status";
import type { EventSummary } from "@/lib/types";
import { Caption, EmptyState, Progress, StatusPill } from "./ui";
import styles from "./event.module.css";

/** イベント一覧（DESIGN.md「Data Table」）。題名 ／ 日時 ／ 幹事 ／ いまの段階 ／ 承諾 ／ 送金の進捗 */
export function EventTable({ events }: { events: EventSummary[] }) {
  const href = useDemoHref();
  if (events.length === 0) {
    return (
      <EmptyState title="イベントはまだありません">KUROKOに依頼すると、ここにイベントが並びます。</EmptyState>
    );
  }
  return (
    <>
      <div className={`${styles.tableWrap} ${styles.desktopTable}`} style={{ background: "var(--surface-card)" }}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">題名</th>
              <th scope="col">日時</th>
              <th scope="col">幹事</th>
              <th scope="col">いまの段階</th>
              <th scope="col" className={styles.num}>
                承諾
              </th>
              <th scope="col" style={{ minWidth: "calc(var(--spacing-80) * 2)" }}>
                送金の進捗
              </th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.eventId}>
                <td>
                  <Link href={href(`/events/${e.eventId}`)} className={styles.personName}>
                    {e.title}
                  </Link>
                  {e.sandbox && <Caption>体験用（7日で削除）</Caption>}
                </td>
                <td className={styles.num} style={{ textAlign: "left" }}>
                  {formatDateTime(e.datetime)}
                </td>
                <td>{e.organizerName}</td>
                <td>
                  <StatusPill view={EVENT_STATUS[e.status]} />
                </td>
                <td className={styles.num}>
                  {e.consentTargetCount > 0 ? `${e.consentedCount} / ${e.consentTargetCount}名` : "—"}
                </td>
                <td>
                  {e.billedYen > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-4)" }}>
                      <span className={styles.timeCell} style={{ textAlign: "left" }}>
                        {e.paidYen.toLocaleString("ja-JP")} / {formatYen(e.billedYen)}
                      </span>
                      <Progress value={e.paidYen} max={e.billedYen} label={`${e.title} の送金の進捗`} />
                    </div>
                  ) : (
                    <span className={styles.timeCell} style={{ textAlign: "left" }}>
                      按分の前
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className={styles.mobileRows}>
        {events.map((e) => (
          <li key={e.eventId} className={styles.mobileRow} style={{ background: "var(--surface-card)" }}>
            <Link href={href(`/events/${e.eventId}`)} className={styles.personName}>
              {e.title}
            </Link>
            <StatusPill view={EVENT_STATUS[e.status]} />
            <Caption>
              {formatDateTime(e.datetime)} ／ 幹事 {e.organizerName}
              {e.consentTargetCount > 0 ? ` ／ 承諾 ${e.consentedCount}/${e.consentTargetCount}名` : ""}
            </Caption>
          </li>
        ))}
      </ul>
    </>
  );
}
