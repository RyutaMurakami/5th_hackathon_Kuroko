"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useDemoHref, useDemoRole } from "@/lib/demo";
import { Icon } from "./Icon";
import { NotificationBell } from "./NotificationBell";
import { Pill, TextButton } from "./ui";
import styles from "./shell.module.css";

const ROLE_LABEL = { organizer: "幹事", guest: "ゲスト" } as const;

export function AppHeader() {
  const role = useDemoRole();
  const href = useDemoHref();
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const onEvents = pathname.startsWith("/events");

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
        {/* ログインの前は、役割と通知を出さない */}
        {user && (
        <div className={styles.right}>
          <Pill tone="navy">{ROLE_LABEL[role]}</Pill>
          <NotificationBell />
          <span className={styles.account} title={user.email ?? undefined}>
            <Icon name="user" label={user.displayName ?? user.email ?? "アカウント"} />
          </span>
          <TextButton onClick={() => void signOut()}>ログアウト</TextButton>
        </div>
        )}
      </div>
    </header>
  );
}
