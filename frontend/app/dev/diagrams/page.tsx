import { Card, TextLink } from "@/components/ui";
import { GITHUB_BLOB } from "@/lib/dev-docs-registry";
import { diagrams } from "@/lib/dev-docs";
import styles from "@/components/dev.module.css";

/** Diagram Viewer（DESIGN.md）。draw.io の図を CLI で SVG に書き出したもの（docs/diagrams/export/） */
export default function DevDiagramsPage() {
  const list = diagrams();
  if (list.length === 0) {
    return (
      <Card>
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>構成図はまだありません</p>
          <p>docs/diagrams/export/ に SVG を書き出すと、ここに出ます。</p>
        </div>
      </Card>
    );
  }
  return (
    <>
      {list.map((d) => {
        const src = `/dev/diagrams/file/${d.id}`;
        return (
          <Card
            key={d.file}
            title={d.title}
            description={<span className={styles.docPath}>{d.source}</span>}
            actions={
              <span className={styles.actionsRow}>
                <TextLink href={src} external>
                  原寸で開く
                </TextLink>
                <TextLink href={`${GITHUB_BLOB}/${encodeURI(d.source)}`} external>
                  元の図（GitHub）
                </TextLink>
              </span>
            }
          >
            <div className={styles.diagramFrame}>
              {/* eslint-disable-next-line @next/next/no-img-element -- SVG をそのまま出す（最適化の対象外） */}
              <img className={styles.diagramImage} src={src} alt={`${d.title}の図`} loading="lazy" />
            </div>
          </Card>
        );
      })}
    </>
  );
}
