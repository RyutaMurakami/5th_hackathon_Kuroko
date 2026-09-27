import Link from "next/link";
import { Eyebrow } from "@/components/ui";
import { DEV_DOCS } from "@/lib/dev-docs-registry";
import styles from "@/components/dev.module.css";

export default function DevDocsPage() {
  return (
    <div className={styles.docGrid}>
      {DEV_DOCS.map((d) => (
        <Link key={d.slug} href={`/dev/docs/${d.slug}`} className={styles.docCard}>
          <Eyebrow>{d.eyebrow}</Eyebrow>
          <span className={styles.docCardTitle}>{d.title}</span>
          <span className={styles.docCardText}>{d.description}</span>
          <span className={styles.docPath}>{d.path}</span>
        </Link>
      ))}
    </div>
  );
}
