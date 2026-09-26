import { formatDateTime, formatTime, formatYen } from "@/lib/format";
import { PAYMENT_STATUS } from "@/lib/status";
import type { Participant, Payment } from "@/lib/types";
import { Icon } from "./Icon";
import { Avatar, Caption, Card, EmptyState, OutlinePill, Progress, RoleBadge, StatusPill } from "./ui";
import styles from "./event.module.css";

/** 誰から誰へ、いくら送金されたか（DESIGN.md「Payment Table」） */
export function PaymentTable({
  payments,
  participants,
}: {
  payments: Payment[];
  participants: Participant[];
}) {
  const nameOf = (userId: string) => participants.find((p) => p.userId === userId)?.displayName ?? userId;
  const paid = payments.filter((p) => p.status === "completed").reduce((sum, p) => sum + p.amountYen, 0);
  const billed = payments.reduce((sum, p) => sum + p.amountYen, 0);

  return (
    <Card eyebrow="送金" title="誰から誰へ、いくら">
      {/* 送金の一覧には常に出す。「送金していない」と読める文言にしない */}
      <div className={styles.sandboxNote}>
        <OutlinePill>sunabar（サンドボックス）</OutlinePill>
        <Caption>銀行API経由で送金を実行しています。サンドボックス環境のため資金は仮想です</Caption>
      </div>

      {payments.length === 0 ? (
        <EmptyState title="まだ振込はありません">按分が承認されると、ここに振込の依頼と状況が並びます。</EmptyState>
      ) : (
        <>
          <div className={`${styles.tableWrap} ${styles.desktopTable}`}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">送金元 → 送金先</th>
                  <th scope="col" className={styles.num}>
                    金額
                  </th>
                  <th scope="col">状態</th>
                  <th scope="col" className={styles.num}>
                    日時
                  </th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.paymentId}>
                    <td>
                      <div className={styles.person}>
                        <Avatar name={nameOf(p.payerUserId)} size="xs" />
                        <span className={styles.personName}>{nameOf(p.payerUserId)}</span>
                        <span className={styles.arrow}>
                          <Icon name="arrowRight" size="sm" label="から" />
                        </span>
                        <span className={styles.personName}>{nameOf(p.payeeUserId)}</span>
                        <RoleBadge role="organizer" />
                      </div>
                    </td>
                    <td className={`${styles.num} ${styles.amount}`}>{formatYen(p.amountYen)}</td>
                    <td>
                      <StatusPill view={PAYMENT_STATUS[p.status]} />
                      <PaymentNote payment={p} />
                    </td>
                    <td className={styles.timeCell}>{p.updatedAt ? formatDateTime(p.updatedAt) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className={styles.mobileRows}>
            {payments.map((p) => (
              <li key={p.paymentId} className={styles.mobileRow}>
                <span>
                  {nameOf(p.payerUserId)} → {nameOf(p.payeeUserId)}
                </span>
                <span className={styles.amount}>{formatYen(p.amountYen)}</span>
                <StatusPill view={PAYMENT_STATUS[p.status]} />
              </li>
            ))}
          </ul>

          <div className={styles.tableFooter}>
            <div className={styles.footerLine}>
              <span>送金済み</span>
              <span className={styles.footerStrong}>
                {paid.toLocaleString("ja-JP")} / {formatYen(billed)}
              </span>
            </div>
            <Progress value={paid} max={billed} label="送金の進捗" />
          </div>
        </>
      )}
    </Card>
  );
}

function PaymentNote({ payment }: { payment: Payment }) {
  if (payment.status === "awaiting_bank_approval" && payment.approvalDeadline) {
    return (
      <span className={styles.cellNote}>
        期限 {formatTime(payment.approvalDeadline)}
        {payment.retryCount > 0 ? `・作り直し ${payment.retryCount}回` : ""}
      </span>
    );
  }
  if ((payment.status === "blocked" || payment.status === "failed") && payment.blockReason) {
    return <span className={`${styles.cellNote} ${styles.cellNoteCoral}`}>{payment.blockReason}</span>;
  }
  return null;
}
