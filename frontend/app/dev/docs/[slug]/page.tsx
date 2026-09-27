import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DevMarkdown } from "@/components/DevMarkdown";
import { Card, Eyebrow, TextLink } from "@/components/ui";
import { DEV_DOCS, GITHUB_BLOB, docBySlug } from "@/lib/dev-docs-registry";
import { readDoc, toc, type TocItem } from "@/lib/dev-docs";
import styles from "@/components/dev.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return DEV_DOCS.map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const doc = docBySlug((await params).slug);
  return { title: doc ? `${doc.title} | 開発者 | KUROKO` : "開発者 | KUROKO" };
}

function TocList({ items }: { items: TocItem[] }) {
  return (
    <ol className={styles.tocList}>
      {items.map((item) => (
        <li key={item.id} className={item.depth === 3 ? styles.tocDepth3 : undefined}>
          <a href={`#${item.id}`}>{item.text}</a>
        </li>
      ))}
    </ol>
  );
}

/** Doc Reader（DESIGN.md） */
export default async function DevDocPage({ params }: { params: Promise<{ slug: string }> }) {
  const doc = docBySlug((await params).slug);
  if (!doc) notFound();
  const md = readDoc(doc);
  const items = toc(md);

  return (
    <div className={styles.reader}>
      <aside className={styles.toc} aria-label="目次">
        <p className={styles.tocTitle}>目次</p>
        <TocList items={items} />
      </aside>
      <Card as="article">
        <div className={styles.docHead}>
          <Eyebrow>{doc.eyebrow}</Eyebrow>
          <span className={styles.docPath}>{doc.path}</span>
          <TextLink href={`${GITHUB_BLOB}/${doc.path}`} external>
            GitHub で開く
          </TextLink>
        </div>
        <details className={styles.tocMobile}>
          <summary>目次</summary>
          <TocList items={items} />
        </details>
        <div className={styles.docBody}>
          <DevMarkdown source={md} fromFile={doc.path} />
        </div>
      </Card>
    </div>
  );
}
