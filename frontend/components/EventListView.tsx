"use client";

import { useDemoHref, useDemoRole } from "@/lib/demo";
import { useEventList } from "@/lib/data";
import { EventTable } from "./EventTable";
import { ButtonLink, ErrorBanner, InfoBanner } from "./ui";
import styles from "./event.module.css";

export function EventListView() {
  const role = useDemoRole();
  const href = useDemoHref();
  const { data: events, loading, error } = useEventList(role);

  return (
    <main className={styles.page}>
      <div className={styles.pageHead}>
        <div>
          <h1 className={styles.pageTitle}>イベント</h1>
          <p className={styles.pageMeta}>
            {role === "guest" ? "あなたが作った体験用のイベント" : "あなたが幹事のイベント"}
          </p>
        </div>
        <ButtonLink href={href("/")}>新しく依頼する</ButtonLink>
      </div>
      <InfoBanner>
        委任・承認・取り消しは Slack で行います。予約内容と領収書の金額の確認は、この画面でできます。
      </InfoBanner>
      {error && <ErrorBanner>一覧を読み込めませんでした。少し待って、もう一度お試しください。</ErrorBanner>}
      {loading ? null : <EventTable events={events ?? []} />}
    </main>
  );
}
