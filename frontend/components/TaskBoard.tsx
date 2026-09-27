"use client";

import { useEffect, useMemo, useState } from "react";
import type { DevTask } from "@/lib/dev-docs";
import { DevMarkdown } from "./DevMarkdown";
import { Tabs } from "./Tabs";
import { Card, Pill } from "./ui";
import styles from "./dev.module.css";

type Kind = "ai" | "human";
type Status = "open" | "done" | "all";

const SOURCE: Record<Kind, string> = { ai: "docs/TASKS.md", human: "docs/human_task.md" };

/** Task Board（DESIGN.md）。正は文書なので、編集の操作は置かない */
export function TaskBoard({
  ai,
  human,
  groupNames,
}: {
  ai: DevTask[];
  human: DevTask[];
  /** 観点・フェーズの表示名（例: E → 「E. 環境準備系」） */
  groupNames: Record<string, string>;
}) {
  const [kind, setKind] = useState<Kind>("ai");
  const [status, setStatus] = useState<Status>("open");
  const [group, setGroup] = useState<string>("all");
  const [openId, setOpenId] = useState<string | null>(null);

  // 概要からのリンク（/dev/tasks?group=E、/dev/tasks#H11）で、絞り込み・開いた状態にする
  useEffect(() => {
    const initialGroup = new URLSearchParams(window.location.search).get("group");
    if (initialGroup && ai.some((t) => t.group === initialGroup)) setGroup(initialGroup);
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (!id) return;
    const inHuman = human.some((t) => t.id === id);
    if (!inHuman && !ai.some((t) => t.id === id)) return;
    setKind(inHuman ? "human" : "ai");
    setStatus("all");
    setOpenId(id);
    requestAnimationFrame(() => document.getElementById(`task-${id}`)?.scrollIntoView({ block: "center" }));
  }, [ai, human]);

  const tasks = kind === "ai" ? ai : human;
  const groups = useMemo(() => [...new Set(tasks.map((t) => t.group))], [tasks]);
  const shown = tasks.filter(
    (t) => (status === "all" || (status === "done") === t.done) && (group === "all" || t.group === group),
  );
  const openCount = tasks.filter((t) => !t.done).length;

  return (
    <Card>
      <div className={styles.boardControls}>
        <Tabs<Kind>
          label="タスクの種類"
          value={kind}
          onChange={(v) => {
            setKind(v);
            setGroup("all");
          }}
          items={[
            { value: "ai", label: "AI のタスク", meta: `${ai.filter((t) => !t.done).length}` },
            { value: "human", label: "人間のタスク", meta: `${human.filter((t) => !t.done).length}`, dot: "sun" },
          ]}
        />
        <Tabs<Status>
          label="状態"
          size="sm"
          value={status}
          onChange={setStatus}
          items={[
            { value: "open", label: "未完了" },
            { value: "done", label: "完了" },
            { value: "all", label: "すべて" },
          ]}
        />
        <div className={styles.chipRow} role="group" aria-label={kind === "ai" ? "観点" : "フェーズ"}>
          {["all", ...groups].map((g) => (
            <button
              key={g}
              type="button"
              aria-pressed={group === g}
              className={`${styles.chipButton} ${group === g ? styles.chipButtonActive : ""}`}
              onClick={() => setGroup(g)}
            >
              {g === "all" ? "すべて" : (groupNames[g] ?? g)}
            </button>
          ))}
        </div>
      </div>

      <p className={styles.boardCount}>
        未完了 {openCount} / 全体 {tasks.length}（表示 {shown.length}）
      </p>

      {shown.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>該当するタスクはありません</p>
          <p>絞り込みを変えると、ほかのタスクが出ます。</p>
        </div>
      ) : (
        <ul className={styles.taskList}>
          {shown.map((t) => {
            const open = openId === t.id;
            return (
              <li key={t.id} id={`task-${t.id}`} className={styles.taskItem}>
                <button
                  type="button"
                  className={styles.taskRow}
                  aria-expanded={open}
                  onClick={() => setOpenId(open ? null : t.id)}
                >
                  <span className={styles.taskId}>{t.id}</span>
                  <span className={styles.taskMain}>
                    <span className={styles.taskTitle}>{t.title}</span>
                    <span className={styles.taskSection}>
                      {t.kind ? `【${t.kind}】 ` : ""}
                      {t.section}
                    </span>
                  </span>
                  {t.done ? (
                    <Pill tone="lagoon">完了</Pill>
                  ) : kind === "human" ? (
                    <Pill tone="sun">人の対応待ち</Pill>
                  ) : (
                    <Pill tone="slate">未完了</Pill>
                  )}
                </button>
                {open && (
                  <div className={styles.taskBody}>
                    <DevMarkdown source={t.body} fromFile={SOURCE[kind]} compact />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
