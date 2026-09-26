"use client";

import { useDemoHref, useDemoRole } from "@/lib/demo";
import { Icon } from "./Icon";
import { TextLink } from "./ui";
import styles from "./shell.module.css";

/** ゲスト（審査員）の画面に常に出す。閉じるボタンは付けない（SPEC 7.6） */
export function GuestBanner() {
  const role = useDemoRole();
  const href = useDemoHref();
  if (role !== "guest") return null;
  return (
    <div className={styles.guestBanner} role="note">
      <div className={styles.guestBannerInner}>
        <Icon name="info" />
        <p className={styles.guestBannerText}>
          <strong>審査員として体験中です</strong>。ここのデータは架空で、<strong>7日で削除されます</strong>
          。送金は sunabar（銀行APIのサンドボックス）で、資金は仮想です。
        </p>
        <TextLink href={`${href("/")}#how-to`}>使い方</TextLink>
      </div>
    </div>
  );
}
