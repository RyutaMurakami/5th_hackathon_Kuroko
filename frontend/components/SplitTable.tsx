"use client";

import { useState } from "react";
import { formatDateTime, formatWeight, formatYen } from "@/lib/format";
import { MEMBER_CLASS_LABEL } from "@/lib/status";
import type { Participant, SplitResult } from "@/lib/types";
import { Icon } from "./Icon";
import { Avatar, Caption, Card, Eyebrow, Nested, StatBlock, StatusPill, TextButton } from "./ui";
import styles from "./event.module.css";

/**
 * 按分の内訳（DESIGN.md「Split Table」、SPEC 7.3.1）。
 * 表示専用。数字は API（SplitResult）の値をそのまま出し、Web では再計算も編集もしない。
 */
export function SplitTable({ split, participants }: { split: SplitResult; participants: Participant[] }) {
  const [showAllQuotes, setShowAllQuotes] = useState(false);
  const nameOf = (userId: string) => participants.find((p) => p.userId === userId)?.displayName ?? userId;
  const quotes = showAllQuotes ? split.policyQuotes : split.policyQuotes.slice(0, 1);
  const approved = split.approval.status === "approved";

  const flow = [
    { label: "会計金額", value: split.totalAmountYen },
    { label: "会社補助", value: split.subsidyYen },
    { label: "按分の対象額", value: split.baseAmountYen },
    { label: "1係数あたり", value: split.perWeightYen },
  ];

  return (
    <Card eyebrow="按分" title="誰がいくら払うのか" description={`係数の合計 ${split.weightSum.toFixed(1)}`}>
      <Nested>
        <div className={styles.flow}>
          {flow.map((item, i) => (
            <div key={item.label} style={{ display: "contents" }}>
              {i > 0 && (
                <span className={styles.flowArrow}>
                  <Icon name="arrowRight" />
                </span>
              )}
              <div className={styles.flowItem}>
                <StatBlock label={item.label} value={item.value.toLocaleString("ja-JP")} unit="円" small />
              </div>
            </div>
          ))}
        </div>
      </Nested>

      <div className={`${styles.tableWrap} ${styles.desktopTable}`} style={{ marginTop: "var(--spacing-16)" }}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">名前</th>
              <th scope="col">区分</th>
              <th scope="col" className={styles.num}>
                係数
              </th>
              <th scope="col">会社補助</th>
              <th scope="col" className={styles.num}>
                負担額
              </th>
            </tr>
          </thead>
          <tbody>
            {split.rows.map((row) => (
              <tr key={row.userId}>
                <td>
                  <div className={styles.person}>
                    <Avatar name={nameOf(row.userId)} size="xs" />
                    <span className={styles.personName}>{nameOf(row.userId)}</span>
                  </div>
                </td>
                <td>{row.memberClass ? MEMBER_CLASS_LABEL[row.memberClass] : "主役"}</td>
                <td className={styles.num}>{row.weight > 0 ? formatWeight(row.weight) : "—"}</td>
                <td>{row.subsidyEligible ? "対象" : "対象外"}</td>
                <td className={styles.num}>
                  <ShareCell billed={row.billed} shareYen={row.shareYen} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className={styles.mobileRows} style={{ marginTop: "var(--spacing-16)" }}>
        {split.rows.map((row) => (
          <li key={row.userId} className={styles.mobileRow}>
            <span>
              {nameOf(row.userId)}（{row.memberClass ? MEMBER_CLASS_LABEL[row.memberClass] : "主役"}
              {row.weight > 0 ? `・${formatWeight(row.weight)}` : ""}）
            </span>
            <ShareCell billed={row.billed} shareYen={row.shareYen} />
          </li>
        ))}
      </ul>

      <div className={styles.tableFooter}>
        <div className={styles.footerLine}>
          <span>負担額の合計</span>
          <span className={styles.footerStrong}>{formatYen(split.shareTotalYen)}</span>
        </div>
        {split.shortfallYen > 0 && split.shortfallTo && (
          <Caption>
            端数の不足 {formatYen(split.shortfallYen)}は {nameOf(split.shortfallTo)} が負担します
          </Caption>
        )}
      </div>

      <Nested className={styles.quotes}>
        {quotes.map((q) => (
          <div key={q.article}>
            <Eyebrow>{q.article}</Eyebrow>
            <p className={styles.quoteText}>{q.text}</p>
          </div>
        ))}
        {split.policyQuotes.length > 1 && (
          <div>
            <TextButton onClick={() => setShowAllQuotes((v) => !v)} aria-expanded={showAllQuotes}>
              {showAllQuotes ? "閉じる" : "続きを読む"}
            </TextButton>
          </div>
        )}
      </Nested>

      <div className={styles.approvalRow}>
        <span>承認者 {nameOf(split.approval.approverUserId)}</span>
        <StatusPill view={approved ? { label: "承認済み", tone: "lagoon" } : { label: "承認待ち", tone: "sun" }} />
        {approved && split.approval.approvedAt && (
          <>
            <Caption>{formatDateTime(split.approval.approvedAt)}</Caption>
            <span className={styles.mono}>hash {split.approval.splitHash.slice(0, 8)}</span>
          </>
        )}
      </div>
    </Card>
  );
}

function ShareCell({ billed, shareYen }: { billed: boolean; shareYen: number }) {
  if (billed) return <span className={styles.amount}>{formatYen(shareYen)}</span>;
  return (
    <span className={styles.cellNote} style={{ marginTop: 0 }}>
      請求なし{shareYen > 0 ? `（本人の負担 ${formatYen(shareYen)}）` : ""}
    </span>
  );
}
