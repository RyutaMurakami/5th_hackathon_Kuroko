"use client";

// 共通の小さな部品。見た目は ui.module.css（DESIGN.md のトークンだけを使う）。
import { motion } from "motion/react";
import Link from "next/link";
import { DURATION, EASE_OUT } from "@/lib/motion";
import { initialOf } from "@/lib/format";
import { PARTICIPANT_ROLE_LABEL, type StatusView, type Tone } from "@/lib/status";
import type { ParticipantRole } from "@/lib/types";
import { Icon } from "./Icon";
import styles from "./ui.module.css";

type ButtonVariant = "primary" | "secondary";

export function Button({
  variant = "primary",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      type="button"
      {...props}
      className={[styles.button, styles[variant], className].filter(Boolean).join(" ")}
    />
  );
}

export function ButtonLink({
  variant = "primary",
  href,
  children,
  external,
}: {
  variant?: ButtonVariant;
  href: string;
  children: React.ReactNode;
  external?: boolean;
}) {
  const className = [styles.button, styles[variant]].join(" ");
  if (external) {
    return (
      <a className={className} href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  }
  return (
    <Link className={className} href={href}>
      {children}
    </Link>
  );
}

export function TextButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" {...props} className={styles.textButton} />;
}

export function TextLink({
  href,
  children,
  external,
}: {
  href: string;
  children: React.ReactNode;
  external?: boolean;
}) {
  if (external) {
    return (
      <a className={styles.textButton} href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  }
  return (
    <Link className={styles.textButton} href={href}>
      {children}
    </Link>
  );
}

export function StatusPill({ view }: { view: StatusView }) {
  return <Pill tone={view.tone}>{view.label}</Pill>;
}

export function Pill({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className={`${styles.pill} ${styles[`tone-${tone}`]}`}>
      <span className={styles.dot} aria-hidden />
      {children}
    </span>
  );
}

/** 「sunabar（サンドボックス）」など、状態ではない印 */
export function OutlinePill({ children }: { children: React.ReactNode }) {
  return <span className={`${styles.pill} ${styles.outlinePill}`}>{children}</span>;
}

export function RoleBadge({ role }: { role: ParticipantRole }) {
  return <span className={`${styles.badge} ${styles[`badge-${role}`]}`}>{PARTICIPANT_ROLE_LABEL[role]}</span>;
}

export function Chip({
  tone = "cloud",
  children,
}: {
  tone?: "cloud" | "subtle" | "sun";
  children: React.ReactNode;
}) {
  return <span className={`${styles.chip} ${styles[`chip-${tone}`]}`}>{children}</span>;
}

export function Avatar({ name, size = "sm" }: { name: string; size?: "xs" | "sm" | "lg" }) {
  const sizeClass = size === "lg" ? styles.avatarLg : size === "xs" ? styles.avatarXs : "";
  return (
    <span className={`${styles.avatar} ${sizeClass}`} aria-hidden>
      {initialOf(name)}
    </span>
  );
}

export function Card({
  eyebrow,
  title,
  description,
  actions,
  children,
  className,
  id,
  as: Tag = "section",
}: {
  eyebrow?: string;
  title?: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  id?: string;
  as?: "section" | "div" | "article";
}) {
  const hasHeader = eyebrow || title || description || actions;
  return (
    <Tag className={[styles.card, className].filter(Boolean).join(" ")} id={id}>
      {hasHeader && (
        <div className={styles.cardHeader}>
          <div>
            {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
            {title && <h2 className={styles.cardTitle}>{title}</h2>}
            {description && <p className={styles.cardDescription}>{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </Tag>
  );
}

export function HighlightCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={[styles.highlight, className].filter(Boolean).join(" ")}>{children}</section>;
}

export function Eyebrow({ children }: { children: string }) {
  // 英字を含む場合だけ大文字・字間（日本語には字間を付けない）
  const latin = /[A-Za-z]/.test(children);
  return <span className={`${styles.eyebrow} ${latin ? styles.eyebrowLatin : ""}`}>{children}</span>;
}

export function Caption({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={[styles.caption, className].filter(Boolean).join(" ")}>{children}</p>;
}

export function Nested({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={[styles.nested, className].filter(Boolean).join(" ")}>{children}</div>;
}

export function InfoBanner({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className={styles.infoBanner} role="note">
      <Icon name="info" />
      <div style={{ flex: 1 }}>{children}</div>
      {action}
    </div>
  );
}

export function ErrorBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className={styles.errorBanner} role="alert">
      <Icon name="alert" />
      <div>{children}</div>
    </div>
  );
}

export function Progress({
  value,
  max,
  label,
  markDone = true,
}: {
  value: number;
  max: number;
  label: string;
  /** 100% で Lagoon にする（件数の横棒のように、完了の意味がないときは false） */
  markDone?: boolean;
}) {
  const ratio = max > 0 ? Math.min(1, value / max) : 0;
  return (
    <div
      className={styles.progress}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-label={label}
    >
      <motion.div
        className={`${styles.progressBar} ${markDone && ratio >= 1 ? styles.progressDone : ""}`}
        initial={false}
        animate={{ width: `${ratio * 100}%` }}
        transition={{ duration: DURATION.slow, ease: EASE_OUT }}
      />
    </div>
  );
}

export function StatBlock({
  label,
  value,
  unit,
  pill,
  small,
}: {
  label: string;
  value: string;
  unit?: string;
  pill?: React.ReactNode;
  small?: boolean;
}) {
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <div className={styles.statValueRow}>
        <span className={`${styles.statValue} ${small ? styles.statValueSm : ""}`}>{value}</span>
        {unit && <span className={styles.statUnit}>{unit}</span>}
        {pill}
      </div>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={styles.empty}>
      <p className={styles.emptyTitle}>{title}</p>
      <p className={styles.emptyText}>{children}</p>
    </div>
  );
}

export { styles as uiStyles };
