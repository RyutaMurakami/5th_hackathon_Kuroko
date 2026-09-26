import { formatDate, formatYen } from "@/lib/format";
import { CONSENT_SORT, CONSENT_STATE } from "@/lib/status";
import type { Participant } from "@/lib/types";
import { Avatar, Card, EmptyState, RoleBadge, StatBlock, StatusPill } from "./ui";
import styles from "./event.module.css";

/** まだ送金の承諾をしていない人は誰か（DESIGN.md「Consent List」） */
export function ConsentList({ participants }: { participants: Participant[] }) {
  const targets = participants.filter((p) => p.consent !== "not_applicable");
  const consented = targets.filter((p) => ["consented", "awaiting_bank_approval", "paid"].includes(p.consent));
  const sorted = [...participants].sort((a, b) => CONSENT_SORT[a.consent] - CONSENT_SORT[b.consent]);

  return (
    <Card eyebrow="承諾" title="送金の承諾">
      {participants.length === 0 ? (
        <EmptyState title="まだ依頼していません">
          イベントの計画を確定すると、Slack で出欠と支払いの委任の依頼が届き、回答がここに並びます。
        </EmptyState>
      ) : (
        <>
          <div style={{ marginBottom: "var(--spacing-16)" }}>
            <StatBlock label="承諾済み" value={`${consented.length} / ${targets.length}`} unit="名" small />
          </div>
          {/* 署名の原文・口座番号・トークンは出さない。上限額と期限だけ */}
          <ul className={styles.consentList}>
            {sorted.map((p) => {
              const view = CONSENT_STATE[p.consent];
              const waiting = p.consent === "pending" || p.consent === "bank_auth_pending";
              return (
                <li key={p.userId} className={`${styles.consentRow} ${waiting ? styles.consentWaiting : ""}`}>
                  <div className={styles.consentMain}>
                    <Avatar name={p.displayName} />
                    <span className={styles.personName}>{p.displayName}</span>
                    <RoleBadge role={p.role} />
                  </div>
                  <div className={styles.consentMeta}>
                    <StatusPill view={view} />
                    {p.capYen !== null && p.mandateExpiresAt && (
                      <span className={styles.consentCaps}>
                        上限 {formatYen(p.capYen)} ／ 期限 {formatDate(p.mandateExpiresAt)}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Card>
  );
}
