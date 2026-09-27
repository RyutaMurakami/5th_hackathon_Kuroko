import Link from "next/link";
import { DevMarkdown } from "@/components/DevMarkdown";
import { Card, HighlightCard, Pill, Progress } from "@/components/ui";
import { DEV_DOCS } from "@/lib/dev-docs-registry";
import { aiTasks, humanTasks, readRepoFile, section } from "@/lib/dev-docs";
import styles from "@/components/dev.module.css";

const ASPECTS: Record<string, string> = {
  E: "環境準備",
  I: "インフラ",
  F: "フロントエンド",
  B: "バックエンド・AI",
  O: "検証・その他",
};

/** 概要（SPEC 7.3.2）。すべて文書から組み立てる（手で書いた要約を置かない） */
export default function DevOverviewPage() {
  const tasksMd = readRepoFile("docs/TASKS.md");
  const planMd = readRepoFile("docs/PLAN.md");
  const archMd = readRepoFile("docs/ARCHITECTURE.md");
  const ai = aiTasks(tasksMd);
  const human = humanTasks();
  const state = /^- 状態: (.+)$/m.exec(tasksMd)?.[1] ?? "";
  const humanOpen = human.filter((t) => !t.done);
  const aiDone = ai.filter((t) => t.done).length;

  return (
    <>
      <HighlightCard>
        <p className={styles.tocTitle}>いまの状態（TASKS.md）</p>
        <DevMarkdown source={state} fromFile="docs/TASKS.md" compact />
      </HighlightCard>

      <Card
        eyebrow="進捗"
        title={`AI のタスク ${aiDone} / ${ai.length} 完了`}
        description="観点ごとの完了数。押すと、その観点の未完了のタスクへ。"
      >
        <div className={styles.statGrid}>
          {Object.entries(ASPECTS).map(([key, name]) => {
            const list = ai.filter((t) => t.group === key);
            const done = list.filter((t) => t.done).length;
            return (
              <Link key={key} href={`/dev/tasks?group=${key}`} className={styles.statCell}>
                <span className={styles.statName}>
                  {key}. {name}
                </span>
                <span className={styles.statNumbers}>
                  {done} <small>/ {list.length}</small>
                </span>
                <Progress value={done} max={list.length} label={`${name}の完了数`} />
              </Link>
            );
          })}
        </div>
      </Card>

      <div className={styles.twoCol}>
        <Card
          eyebrow="人の対応待ち"
          title={`人間の未完了タスク ${humanOpen.length}件`}
          description="human_task.md。AI の実装はここで止まっていることがある。"
        >
          <div className={styles.linkList}>
            {humanOpen.map((t) => (
              <Link key={t.id} href={`/dev/tasks#${t.id}`} className={styles.linkItem}>
                <span className={styles.mono}>{t.id}</span>
                <span className={styles.linkItemMain}>
                  <span className={styles.linkItemTitle}>{t.title}</span>
                  <span className={styles.linkItemNote}>{t.section}</span>
                </span>
                <Pill tone="sun">{t.kind ?? "人"}</Pill>
              </Link>
            ))}
          </div>
        </Card>

        <Card eyebrow="文書" title="どこに何が書いてあるか" description="食い違ったら SPEC が正。">
          <div className={styles.linkList}>
            {DEV_DOCS.map((d) => (
              <Link key={d.slug} href={`/dev/docs/${d.slug}`} className={styles.linkItem}>
                <span className={styles.linkItemMain}>
                  <span className={styles.linkItemTitle}>{d.title}</span>
                  <span className={styles.linkItemNote}>{d.description}</span>
                </span>
              </Link>
            ))}
          </div>
        </Card>
      </div>

      <Card eyebrow="KUROKO とは" title="現行版の要約（PLAN.md）">
        <DevMarkdown source={section(planMd, "現行版の要約")} fromFile="docs/PLAN.md" />
      </Card>

      <Card eyebrow="構成" title="構成図（ARCHITECTURE.md 2.3）" description="配備と信頼境界。draw.io の図は「構成図」タブ。">
        <DevMarkdown source={section(archMd, "2.3")} fromFile="docs/ARCHITECTURE.md" />
      </Card>

      <Card eyebrow="構成" title="デプロイ単位の一覧（ARCHITECTURE.md 2.2）">
        <DevMarkdown source={section(archMd, "2.2")} fromFile="docs/ARCHITECTURE.md" />
      </Card>
    </>
  );
}
