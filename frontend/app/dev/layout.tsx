import type { Metadata } from "next";
import { DevNav } from "@/components/DevNav";
import { contentMeta } from "@/lib/dev-docs";
import styles from "@/components/event.module.css";

// 開発者ページ（SPEC 7.3.2）。内部の文書なので、検索エンジンに載せない
export const metadata: Metadata = { title: "開発者 | KUROKO", robots: { index: false, follow: false } };

export default function DevLayout({ children }: { children: React.ReactNode }) {
  const meta = contentMeta();
  const synced = new Date(meta.syncedAt).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" });
  return (
    <main className={styles.page}>
      <div>
        <h1 className={styles.pageTitle}>開発者</h1>
        <p className={styles.pageMeta}>
          システムの全体像・構成・残りのタスク。内容はリポジトリの文書（{synced} 時点
          {meta.commit ? `・${meta.commit.slice(0, 7)}` : ""}）で、ここでは編集しない。
        </p>
      </div>
      <DevNav />
      {children}
    </main>
  );
}
