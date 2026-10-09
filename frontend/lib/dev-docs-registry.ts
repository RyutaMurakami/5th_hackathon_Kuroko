// 開発者ページ（/dev。SPEC 7.3.2）で扱う文書の一覧と、文書の間のリンクの張り替え。
// ブラウザ側（タスクの本文の表示）でも使うので、node の API を使わない。

export const GITHUB_BLOB = "https://github.com/RyutaMurakami/5th_hackathon_Kuroko/blob/main";

export type DevDoc = {
  slug: string;
  /** リポジトリのルートからのパス（frontend/content/ にも同じパスで写してある） */
  path: string;
  title: string;
  eyebrow: string;
  description: string;
};

export const DEV_DOCS: DevDoc[] = [
  { slug: "plan", path: "docs/PLAN.md", title: "概要（PLAN）", eyebrow: "概要", description: "課題・想定ユーザー・コンセプト・競合との差分・前提とスコープ外" },
  { slug: "spec", path: "docs/SPEC.md", title: "仕様（SPEC）", eyebrow: "仕様", description: "機能要件・API・データモデル・ツール契約・エージェント設計。食い違ったらこれが正" },
  { slug: "architecture", path: "docs/ARCHITECTURE.md", title: "アーキテクチャ（ARCHITECTURE）", eyebrow: "アーキテクチャ", description: "サービス・コード配置・権限・デプロイ・決定（D）と要検証（V）" },
  { slug: "design", path: "DESIGN.md", title: "UI デザイン（DESIGN）", eyebrow: "デザイン", description: "Web の見た目と部品の規約（トークン・コンポーネント）" },
  { slug: "tasks", path: "docs/TASKS.md", title: "AI のタスク（TASKS）", eyebrow: "タスク", description: "エージェントが行う実装タスク（観点 E・I・F・B・O）" },
  { slug: "human-task", path: "docs/human_task.md", title: "人間のタスク（human_task）", eyebrow: "タスク", description: "アカウント・申請・承認・提出など、人が行うタスクと秘密の受け渡し" },
  { slug: "h11-guide", path: "docs/guides/h11_agent_platform_lab.md", title: "H11 手順書（Agent Platform）", eyebrow: "手順書", description: "Agent Runtime・Gateway・Registry・Model Armor を Console で構築する手順" },
  { slug: "agent-platform-steps", path: "docs/guides/agent_platform_human_steps.md", title: "Agent Platform のチェックリスト", eyebrow: "手順書", description: "Agent Platform の Console 作業のうち、人が行うものを順に並べたチェックリスト" },
  { slug: "demo-run", path: "docs/guides/demo_run.md", title: "デモの通しの実行手順", eyebrow: "手順書", description: "Slack の出欠・承認から、銀行での承認・入金の確認までを実機で通す手順" },
  { slug: "sunabar-guide", path: "docs/guides/h25_sunabar_setup.md", title: "sunabar 手順書", eyebrow: "手順書", description: "口座の割り当て・トークンの登録・疎通の確認（H23・P3・H25・O1）" },
];

export function docBySlug(slug: string): DevDoc | undefined {
  return DEV_DOCS.find((d) => d.slug === slug);
}

/** `a/b/../c` のような相対パスを、リポジトリのルートからのパスにする */
function resolvePath(fromFile: string, href: string): string {
  const parts = fromFile.split("/").slice(0, -1);
  for (const seg of href.split("/")) {
    if (seg === "" || seg === ".") continue;
    if (seg === "..") parts.pop();
    else parts.push(seg);
  }
  return parts.join("/");
}

/**
 * 文書の中のリンクを張り替える。開発者ページにある文書は `/dev/docs/<slug>`、
 * ない文書（review など）は GitHub のファイル、外部の URL と `#` だけのリンクはそのまま。
 */
export function rewriteDocHref(fromFile: string, href: string): { href: string; external: boolean } {
  if (/^[a-z]+:/i.test(href) || href.startsWith("#") || href.startsWith("/")) {
    return { href, external: /^https?:/i.test(href) };
  }
  const [target, hash] = href.split("#");
  const resolved = resolvePath(fromFile, decodeURI(target));
  const doc = DEV_DOCS.find((d) => d.path === resolved);
  if (doc) return { href: `/dev/docs/${doc.slug}${hash ? `#${hash}` : ""}`, external: false };
  return { href: `${GITHUB_BLOB}/${encodeURI(resolved)}${hash ? `#${hash}` : ""}`, external: true };
}
