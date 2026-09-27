// 開発者ページ（/dev。SPEC 7.3.2、ARCHITECTURE D26）用に、リポジトリの文書と構成図を frontend/content/ に写す。
// npm の predev / prebuild と、deploy.yml（Docker のビルドコンテキストが frontend/ だけなので、その前）で実行する。
// リポジトリの文書が見つからないとき（Docker の中のビルド）は、先に写してある content/ をそのまま使う。
import { execSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(frontendDir, "..");
const out = path.join(frontendDir, "content");

if (!existsSync(path.join(repoRoot, "docs", "SPEC.md"))) {
  if (existsSync(path.join(out, "meta.json"))) {
    console.log("sync-docs: リポジトリの文書が見つからないので、同梱済みの content/ を使う");
    process.exit(0);
  }
  console.error("sync-docs: docs/ も content/ もない。リポジトリのルートで node frontend/scripts/sync-docs.mjs を先に実行する");
  process.exit(1);
}

rmSync(out, { recursive: true, force: true });
mkdirSync(path.join(out, "diagrams"), { recursive: true });

const markdown = (name) => name.endsWith(".md");
// 文書はリポジトリ内のパスのまま置く（文書の間の相対リンクを解決するため）
const copyDir = (rel, filter) => {
  const src = path.join(repoRoot, rel);
  if (!existsSync(src)) return;
  for (const name of readdirSync(src).filter(filter)) {
    mkdirSync(path.join(out, rel), { recursive: true });
    cpSync(path.join(src, name), path.join(out, rel, name));
  }
};
copyDir("docs", markdown);
copyDir("docs/guides", markdown);
cpSync(path.join(repoRoot, "DESIGN.md"), path.join(out, "DESIGN.md"));

const exportDir = path.join(repoRoot, "docs", "diagrams", "export");
if (existsSync(exportDir)) {
  for (const name of readdirSync(exportDir).filter((n) => n.endsWith(".svg"))) {
    cpSync(path.join(exportDir, name), path.join(out, "diagrams", name));
  }
}

let commit = process.env.GITHUB_SHA ?? "";
try {
  commit ||= execSync("git rev-parse HEAD", { cwd: repoRoot }).toString().trim();
} catch {
  // git がない環境では空のまま
}
writeFileSync(path.join(out, "meta.json"), JSON.stringify({ syncedAt: new Date().toISOString(), commit }, null, 2));
console.log(`sync-docs: ${out} に写した（commit ${commit.slice(0, 7) || "不明"}）`);
