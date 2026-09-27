"use client";

import { useEffect, useId, useState } from "react";
import styles from "./dev.module.css";

/** Doc Reader の Mermaid の図（DESIGN.md）。描画に失敗したら元のコードをそのまま出す */
export function MermaidDiagram({ code }: { code: string }) {
  const id = `mermaid-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
        const { svg: rendered } = await mermaid.render(id, code);
        if (!cancelled) setSvg(rendered);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [id, code]);

  if (failed) {
    return (
      <pre className={styles.codeBlock}>
        <code>{code}</code>
      </pre>
    );
  }
  return (
    <div className={styles.diagramFrame} aria-busy={svg === null}>
      {/* mermaid が securityLevel: "strict" で無害化した SVG */}
      {svg ? <div dangerouslySetInnerHTML={{ __html: svg }} /> : <div className={styles.diagramPlaceholder} />}
    </div>
  );
}
