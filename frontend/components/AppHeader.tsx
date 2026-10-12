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
  const onDev = pathname.startsWith("/dev");

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
            className={`${styles.navLink} ${pathname.startsWith("/verify") ? styles.navLinkActive : ""}`}
            href="/verify"
            aria-current={pathname.startsWith("/verify") ? "page" : undefined}
          >
            体験
          </Link>
          <Link
            className={`${styles.navLink} ${pathname.startsWith("/demo") ? styles.navLinkActive : ""}`}
            href="/demo"
            aria-current={pathname.startsWith("/demo") ? "page" : undefined}
          >
            実演（開発者）
          </Link>
          <Link
            className={`${styles.navLink} ${onEvents ? styles.navLinkActive : ""}`}
            href={href("/events")}
            aria-current={onEvents ? "page" : undefined}
          >
            状況の一覧
          </Link>
          <Link
            className={`${styles.navLink} ${onDev ? styles.navLinkActive : ""}`}
            href="/dev"
            aria-current={onDev ? "page" : undefined}
          >
            開発資料
          </Link>
        </nav>
        {/* ログインの前は、役割と通知を出さない */}
        {user && (
        <div className={styles.right}>
          <Pill tone="navy">{ROLE_LABEL[role]}</Pill>
          <NotificationBell />
          {/* 実名・メールアドレスは画面にもツールチップにも出さない（DESIGN.md「App Header」） */}
          <span className={styles.account}>
            <Icon name="user" label="アカウント" />
          </span>
          <TextButton onClick={() => void signOut()}>ログアウト</TextButton>
        </div>
        )}
      </div>
    </header>
  );
}
