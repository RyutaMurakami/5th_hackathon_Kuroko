"use client";

// KUROKO が参照している情報（記憶・会社の規程）を見せる（SPEC 7.9）。読むだけ。
import { useEffect, useState } from "react";
import { getReference } from "@/lib/api-client";
import type { ApiReference } from "@/lib/api-types";
import { Button, Caption, Pill } from "./ui";
import styles from "./reference.module.css";

type Tab = "memory" | "policy";

const yen = (n: number) => `${n.toLocaleString("ja-JP")}円`;

export function ReferenceDialog({ eventId, onClose }: { eventId: string | null; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("memory");
  const [data, setData] = useState<ApiReference | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    getReference(eventId)
      .then((d) => alive && setData(d))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [eventId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className={styles.overlay} role="presentation" onClick={onClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-label="KUROKO が参照している情報"
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.head}>
          <h2 className={styles.title}>KUROKO が参照している情報</h2>
          <Button variant="secondary" onClick={onClose}>
            閉じる
          </Button>
        </header>
        <div className={styles.tabs} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "memory"}
            className={`${styles.tab} ${tab === "memory" ? styles.tabActive : ""}`}
            onClick={() => setTab("memory")}
          >
            記憶（Memory Bank）
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "policy"}
            className={`${styles.tab} ${tab === "policy" ? styles.tabActive : ""}`}
            onClick={() => setTab("policy")}
          >
            会社の規程・按分ルール
          </button>
        </div>
        <div className={styles.body}>
          {failed && <p>読み込めませんでした。少し時間をおいて、もう一度開いてください。</p>}
          {!data && !failed && <p>読み込んでいます…</p>}
          {data && tab === "memory" && <MemoryView data={data} />}
          {data && tab === "policy" && <PolicyView data={data} />}
        </div>
      </div>
    </div>
  );
}

function MemoryView({ data }: { data: ApiReference }) {
  const { available, error, groups } = data.memory;
  return (
    <>
      <Caption>
        次の企画のお店選びで、KUROKO が過去の実績として参照します。保存されるのは、定型の事実だけです
        （個人の名前・個人ごとの回答は入りません）。
      </Caption>
      {!available && <p>記憶の保存先が設定されていません。</p>}
      {error && <p>一部の記憶を読み込めませんでした。</p>}
      {groups.map((g) => (
        <section key={g.label} className={styles.group}>
          <h3 className={styles.groupTitle}>
            {g.label} <Pill tone="navy">{g.facts.length}件</Pill>
          </h3>
          {g.facts.length === 0 ? (
            <p className={styles.empty}>まだ記憶はありません。</p>
          ) : (
            <ul className={styles.list}>
              {g.facts.map((f, i) => (
                <li key={i}>{f.text}</li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </>
  );
}

function PolicyView({ data }: { data: ApiReference }) {
  const { policy } = data;
  const v = policy.values;
  return (
    <>
      <Caption>
        {policy.title}（規程番号 {policy.policy_id}・版 {policy.version}）。按分は、この規程から読み取って
        コードで検証した値で、決まった手順で計算します。
      </Caption>
      <section className={styles.group}>
        <h3 className={styles.groupTitle}>
          按分に使う値 <Pill tone={policy.source === "document" ? "lagoon" : "navy"}>
            {policy.source === "document" ? "規程の文書から読み取り" : "既定の値"}
          </Pill>
        </h3>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>負担区分</th>
              <th>負担係数</th>
              <th>委任の上限</th>
            </tr>
          </thead>
          <tbody>
            {v.member_classes.map((c) => (
              <tr key={c.label}>
                <td>{c.label}</td>
                <td>{c.weight}</td>
                <td>{yen(c.consent_cap_yen)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul className={styles.list}>
          <li>
            会社の補助: 1人あたり {yen(v.subsidy_per_attendee_yen)}（1回の上限 {yen(v.subsidy_max_per_event_yen)}）
          </li>
          <li>端数: {yen(v.rounding_unit_yen)}単位で切り捨て。不足は承認者が負担</li>
          <li>コース単価の上限: 1人 {yen(v.hard_limit_per_person_yen)}</li>
          <li>承認者の決め方: {v.approver_selection.join(" → ")}</li>
          <li>お店の帰りやすさ: 全員が {v.venue_max_travel_minutes} 分以内</li>
        </ul>
      </section>
      <section className={styles.group}>
        <h3 className={styles.groupTitle}>条文</h3>
        {policy.articles.map((a) => (
          <details key={a.number} className={styles.article}>
            <summary>
              {a.number}（{a.heading}）
            </summary>
            <p className={styles.articleText}>{a.text}</p>
          </details>
        ))}
      </section>
    </>
  );
}
