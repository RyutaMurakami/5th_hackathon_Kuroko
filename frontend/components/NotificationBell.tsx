"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { useDemoHref, useDemoRole } from "@/lib/demo";
import { formatDateTime } from "@/lib/format";
import { listNotifications } from "@/lib/mock-data";
import { NOTIFICATION_KIND } from "@/lib/status";
import { Icon } from "./Icon";
import { useToast } from "./Toast";
import { StatusPill } from "./ui";
import styles from "./shell.module.css";

export function NotificationBell() {
  const role = useDemoRole();
  const href = useDemoHref();
  const [open, setOpen] = useState(false);
  const [readIds, setReadIds] = useState<string[]>([]);
  const wrapRef = useRef<HTMLDivElement>(null);
  const popoverId = useId();

  // 開発者には通知を出さない（宛先は幹事の UID。SPEC 3章 Notification）
  const { extraNotifications } = useToast();
  const notifications = [...extraNotifications, ...listNotifications(role)]
    .slice(0, 10)
    .map((n) => ({ ...n, read: n.read || readIds.includes(n.notificationId) }));
  const unread = notifications.filter((n) => !n.read).length;

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (role === "developer") return null;

  return (
    <div className={styles.bellWrap} ref={wrapRef}>
      <button
        type="button"
        className={styles.bell}
        aria-label={unread > 0 ? `通知（未読 ${unread}件）` : "通知"}
        aria-expanded={open}
        aria-controls={popoverId}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="bell" />
        {unread > 0 && <span className={styles.unreadDot} aria-hidden />}
      </button>
      {open && (
        <div className={styles.popover} id={popoverId} role="dialog" aria-label="通知">
          <p className={styles.popoverTitle}>通知</p>
          <ul>
            {notifications.map((n) => (
              <li key={n.notificationId}>
                <Link
                  className={`${styles.notification} ${n.read ? "" : styles.unread}`}
                  href={href(`/events/${n.eventId}`)}
                  onClick={() => {
                    setReadIds((ids) => [...ids, n.notificationId]);
                    setOpen(false);
                  }}
                >
                  <StatusPill view={NOTIFICATION_KIND[n.kind]} />
                  <span className={styles.notificationText}>{n.text}</span>
                  <span className={styles.notificationTime}>{formatDateTime(n.createdAt)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
