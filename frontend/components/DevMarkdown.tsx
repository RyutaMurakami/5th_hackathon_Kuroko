// Doc Reader の本文（DESIGN.md）。リポジトリの Markdown を、トークンに沿った書式で出す。
// サーバー（文書のページ）とブラウザ（タスクの本文）の両方で使う。
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";
import { rewriteDocHref } from "@/lib/dev-docs-registry";
import { MermaidDiagram } from "./MermaidDiagram";
import styles from "./dev.module.css";

type CodeNode = { tagName?: string; properties?: { className?: unknown }; children?: { value?: string }[] };

export function DevMarkdown({
  source,
  fromFile,
  compact = false,
}: {
  source: string;
  /** リンクを張り替えるための、元の文書のパス（リポジトリのルートから） */
  fromFile: string;
  /** タスクの本文など、見出しの余白を詰めて出すとき */
  compact?: boolean;
}) {
  const components: Components = {
    a: ({ href = "", children }) => {
      const link = rewriteDocHref(fromFile, href);
      if (link.external) {
        return (
          <a href={link.href} target="_blank" rel="noreferrer">
            {children}
          </a>
        );
      }
      return <Link href={link.href}>{children}</Link>;
    },
    pre: ({ node, children }) => {
      const code = node?.children?.[0] as CodeNode | undefined;
      const className = code?.properties?.className;
      if (code?.tagName === "code" && Array.isArray(className) && className.includes("language-mermaid")) {
        return <MermaidDiagram code={(code.children ?? []).map((c) => c.value ?? "").join("")} />;
      }
      return <pre className={styles.codeBlock}>{children}</pre>;
    },
    table: ({ children }) => (
      <div className={styles.tableWrap}>
        <table>{children}</table>
      </div>
    ),
  };

  return (
    <div className={`${styles.markdown} ${compact ? styles.markdownCompact : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]} components={components}>
        {source}
      </ReactMarkdown>
    </div>
  );
}
