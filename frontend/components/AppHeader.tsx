"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useDemoHref, useDemoRole } from "@/lib/demo";
import { Icon } from "./Icon";
import { NotificationBell } from "./NotificationBell";
import { OutlinePill, Pill } from "./ui";
import styles from "./shell.module.css";

const ROLE_LABEL = { organizer: "幹事", guest: "ゲスト", developer: "開発者" } as const;

export function AppHeader() {
  const role = useDemoRole();
  const href = useDemoHref();
  const pathname = usePathname();
  const params = useSearchParams();
  const onEvents = pathname.startsWith("/events");
  // はじめる画面でログインを選ぶ前は、役割と通知を出さない
  const signedIn = pathname !== "/" || params.has("role");

  return (
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <Link className={styles.brand} href={href("/")}>
          <span className={styles.logo} aria-hidden>
            黒
          </span>
          KUROKO
        </Link>
        <nav className={styles.nav} aria-label="メイン">
          <Link
            className={`${styles.navLink} ${onEvents ? styles.navLinkActive : ""}`}
            href={href("/events")}
            aria-current={onEvents ? "page" : undefined}
          >
            イベント
          </Link>
        </nav>
        {signedIn && (
        <div className={styles.right}>
          <Pill tone="navy">{ROLE_LABEL[role]}</Pill>
          {role === "developer" && (
            <span className={styles.hideSm}>
              <OutlinePill>仮名表示</OutlinePill>
            </span>
          )}
          <NotificationBell />
          <span className={styles.account}>
            <Icon name="user" label="アカウント" />
          </span>
        </div>
        )}
      </div>
    </header>
  );
}
