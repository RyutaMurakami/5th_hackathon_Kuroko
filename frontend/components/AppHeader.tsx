"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getMe } from "@/lib/api-client";
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
  const router = useRouter();
  const onEvents = pathname.startsWith("/events");
  const onDev = pathname.startsWith("/dev");

  // 実演用に登録したアカウントだけが、「体験」以外のタブを見られる（確かめるまでは、出さない）
  const [allowed, setAllowed] = useState(false);
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    if (!user) {
      setAllowed(false);
      setChecked(false);
      return;
    }
    let alive = true;
    getMe()
      .then((me) => alive && (setAllowed(!!me.live_allowed), setChecked(true)))
      .catch(() => alive && (setAllowed(false), setChecked(true)));
    return () => {
      alive = false;
    };
  }, [user]);
  // 登録していないアカウント（ゲスト）は、ログインしたら、トップではなく体験の画面を直接見せる。
  // 実演・一覧・開発資料の URL を直接開いたときも、体験に戻す
  useEffect(() => {
    if (
      user &&
      checked &&
      !allowed &&
      (pathname === "/" || pathname.startsWith("/demo") || onEvents || onDev)
    ) {
      router.replace("/verify");
    }
  }, [user, checked, allowed, pathname, onEvents, onDev, router]);

  return (
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <Link className={styles.brand} href={href("/")}>
          <Image className={styles.logo} src="/avatars/kuroko-logo.png" alt="" width={36} height={36} unoptimized />
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
          {allowed && (
            <>
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
            </>
          )}
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
