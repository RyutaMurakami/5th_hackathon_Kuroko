// 開発者ページ（/dev。SPEC 7.3.2、ARCHITECTURE D26）の文書の読み取りと集計。
// ビルド時にだけ呼ぶ（ページは静的に作る）。文書は scripts/sync-docs.mjs が content/ に写したもの。
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import GithubSlugger from "github-slugger";
import { DEV_DOCS, type DevDoc } from "./dev-docs-registry";

const CONTENT = path.join(process.cwd(), "content");

export function readRepoFile(repoPath: string): string {
  return readFileSync(path.join(CONTENT, repoPath), "utf8");
}

export function readDoc(doc: DevDoc): string {
  return readRepoFile(doc.path);
}

export function contentMeta(): { syncedAt: string; commit: string } {
  return JSON.parse(readRepoFile("meta.json"));
}

// ---------- 見出し・目次・節の切り出し ----------

type Heading = { depth: number; text: string; line: number };

/** コードのまとまり（```）の中を除いた見出し */
function headings(md: string): Heading[] {
  const out: Heading[] = [];
  let fenced = false;
  md.split("\n").forEach((line, i) => {
    if (/^\s*(```|~~~)/.test(line)) fenced = !fenced;
    if (fenced) return;
    const m = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
    if (m) out.push({ depth: m[1].length, text: m[2], line: i });
  });
  return out;
}

/** 見出しの Markdown を、rehype-slug が id を作るときの文字列（表示される文字だけ）にする */
function plainText(inline: string): string {
  return inline
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\*\*|__|`/g, "")
    .replace(/(^|[^\w])\*([^*]+)\*/g, "$1$2")
    .trim();
}

export type TocItem = { depth: number; text: string; id: string };

/** 目次（2・3段目の見出し）。id は rehype-slug と同じ規則・同じ順序の重複回避で作る */
export function toc(md: string): TocItem[] {
  const slugger = new GithubSlugger();
  const items: TocItem[] = [];
  for (const h of headings(md)) {
    const text = plainText(h.text);
    const id = slugger.slug(text);
    if (h.depth === 2 || h.depth === 3) items.push({ depth: h.depth, text, id });
  }
  return items;
}

/** 見出しの文字が `prefix` で始まる節を、次の同じか上の段の見出しの手前まで切り出す */
export function section(md: string, prefix: string, { withHeading = false } = {}): string {
  const lines = md.split("\n");
  const hs = headings(md);
  const start = hs.findIndex((h) => plainText(h.text).startsWith(prefix));
  if (start < 0) return "";
  const end = hs.slice(start + 1).find((h) => h.depth <= hs[start].depth);
  return lines.slice(hs[start].line + (withHeading ? 0 : 1), end ? end.line : undefined).join("\n").trim();
}

// ---------- タスク ----------

export type DevTask = {
  id: string;
  done: boolean;
  /** 観点（E・I・F・B・O）またはフェーズ（Phase 0 など） */
  group: string;
  /** 節の名前（例: 「I-A. Terraform」「D. Agent Runtime・Agent Gateway の検証」） */
  section: string;
  title: string;
  /** 開いたときに出す本文（Markdown） */
  body: string;
  /** 人間のタスクの種別（人・承・決・任意） */
  kind?: string;
};

function firstSentence(markdown: string): string {
  const text = plainText(markdown)
    .replace(/^\d{4}-\d{2}-\d{2}\s*追加[^。]*。\s*/, "")
    .replace(/\s+/g, " ");
  const cut = text.split(/。|:\s|：/)[0];
  return cut.length > 72 ? `${cut.slice(0, 72)}…` : cut;
}

function splitRow(line: string): string[] {
  return line.replace(/^\|\s?/, "").replace(/\s?\|\s*$/, "").split(" | ").map((c) => c.trim());
}

/** TASKS.md の表の行（`| [ ] | E1 | タスク | 人間の依存 | 完了の条件 |`） */
export function aiTasks(md: string = readDoc(DEV_DOCS.find((d) => d.slug === "tasks")!)): DevTask[] {
  const tasks: DevTask[] = [];
  let group = "";
  let sectionName = "";
  let header: string[] = [];
  for (const line of md.split("\n")) {
    const h2 = /^## ([A-Z])\. (.+)$/.exec(line);
    if (h2) {
      group = h2[1];
      sectionName = `${h2[1]}. ${h2[2]}`;
      continue;
    }
    if (/^## /.test(line)) {
      group = "";
      continue;
    }
    const h3 = /^### (.+)$/.exec(line);
    if (h3 && group) sectionName = h3[1];
    if (line.startsWith("| 状態 |")) header = splitRow(line);
    const row = /^\| \[( |x)\] \|/.exec(line);
    if (!row || !group) continue;
    const cells = splitRow(line);
    const cell = (name: string) => cells[header.indexOf(name)] ?? "";
    const task = cell("タスク");
    const body = [
      task,
      cell("人間の依存") && `**人間の依存**: ${cell("人間の依存")}`,
      cell("完了の条件") && `**完了の条件・経過**: ${cell("完了の条件")}`,
    ]
      .filter(Boolean)
      .join("\n\n");
    tasks.push({ id: cells[1], done: row[1] === "x", group, section: sectionName, title: firstSentence(task), body });
  }
  return tasks;
}

/** human_task.md の項目（`- [ ] **H11【人】題名**` と、その下の字下げした行） */
export function humanTasks(md: string = readDoc(DEV_DOCS.find((d) => d.slug === "human-task")!)): DevTask[] {
  const tasks: DevTask[] = [];
  let group = "";
  let sectionName = "";
  let current: DevTask | null = null;
  const bodyLines: string[] = [];
  const flush = () => {
    if (current) tasks.push({ ...current, body: [current.body, bodyLines.join("\n")].filter(Boolean).join("\n\n") });
    current = null;
    bodyLines.length = 0;
  };
  for (const line of md.split("\n")) {
    const h2 = /^## (.+)$/.exec(line);
    if (h2) {
      flush();
      group = h2[1].split(/[:：]/)[0].trim();
      sectionName = h2[1];
      continue;
    }
    const h3 = /^### (.+)$/.exec(line);
    if (h3) {
      flush();
      sectionName = h3[1];
      continue;
    }
    const item = /^- \[( |x)\] \*\*([A-Z]\d+[a-z]?)(【([^】]+)】)?(.*?)\*\*(.*)$/.exec(line);
    if (item) {
      flush();
      current = {
        id: item[2],
        done: item[1] === "x",
        group,
        section: sectionName,
        title: plainText(item[5]),
        body: item[6].trim(),
        kind: item[4],
      };
      continue;
    }
    if (current && (line.startsWith("  ") || line === "")) bodyLines.push(line.replace(/^ {2}/, ""));
    else flush();
  }
  flush();
  return tasks;
}

// ---------- 構成図 ----------

export type Diagram = {
  file: string;
  /** URL に使う名前。日本語のファイル名は静的なルートで引けないので、ファイル名のハッシュにする */
  id: string;
  title: string;
  source: string;
};

/** docs/diagrams/export/*.svg（`drawio` の CLI で書き出したもの）。元の .drawio の名前から題名を作る */
export function diagrams(): Diagram[] {
  const dir = path.join(CONTENT, "diagrams");
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".svg"))
    .sort()
    .map((file) => {
      const base = file.replace(/\.svg$/, "");
      return {
        file,
        id: `${createHash("sha1").update(file).digest("hex").slice(0, 12)}.svg`,
        title: base.replace(/^KUROKO_/, "").replace(/_v[\d.]+$/, "").replace(/_/g, " "),
        source: base.includes("ユーザーフロー") ? `docs/user_flow/${base}.drawio` : `docs/diagrams/${base}.drawio`,
      };
    });
}
