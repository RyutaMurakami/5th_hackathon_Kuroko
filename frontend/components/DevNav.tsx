"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SPRING } from "@/lib/motion";
import detail from "./detail.module.css";
import styles from "./dev.module.css";

const ITEMS = [
  { href: "/dev", label: "概要" },
  { href: "/dev/docs", label: "文書" },
  { href: "/dev/tasks", label: "タスク" },
  { href: "/dev/diagrams", label: "構成図" },
];

/** 開発者ページの Tab Pill Navigation（DESIGN.md）。画面の切り替えなので、ボタンではなくリンクにする */
export function DevNav() {
  const pathname = usePathname();
  const current = ITEMS.filter((i) => pathname === i.href || pathname.startsWith(`${i.href}/`)).at(-1);

  return (
    <nav className={detail.tabBar} aria-label="開発者ページ">
      <div className={detail.tabs}>
        {ITEMS.map((item) => {
          const selected = item === current;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={selected ? "page" : undefined}
              className={`${detail.tab} ${styles.navTab} ${selected ? detail.tabSelected : ""}`}
            >
              {selected && <motion.span layoutId="dev-nav-indicator" className={detail.tabIndicator} transition={SPRING} />}
              <span className={detail.tabLabel}>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
