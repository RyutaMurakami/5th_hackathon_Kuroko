"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { ROLES, isDemoToolbarEnabled, useDemoRole, useDemoStage, useIsEventDetail } from "@/lib/demo";
import { EVENT_STATUS, EVENT_STATUS_ORDER } from "@/lib/status";
import styles from "./shell.module.css";

/**
 * ダミーデータの役割と段階を切り替える開発用の帯（DESIGN.md「Demo Toolbar」）。
 * 見え方を切り替えるだけで、委任・承認・取り消し・振込に当たる操作は置かない。
 */
export function DemoToolbar() {
  const enabled = isDemoToolbarEnabled();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const role = useDemoRole();
  const stage = useDemoStage();
  const onDetail = useIsEventDetail();

  useEffect(() => {
    if (!enabled) return;
    document.body.dataset.demoToolbar = "true";
    return () => {
      delete document.body.dataset.demoToolbar;
    };
  }, [enabled]);

  if (!enabled) return null;

  const update = (next: Record<string, string | null>) => {
    const search = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value === null) search.delete(key);
      else search.set(key, value);
    }
    router.replace(`${pathname}?${search.toString()}`, { scroll: false });
  };

  return (
    <div className={styles.toolbar} role="region" aria-label="デモの切り替え">
      <div className={styles.toolbarInner}>
        <span className={styles.toolbarLabel}>Demo（ダミーデータ）</span>
        <div className={styles.tabs} role="group" aria-label="役割">
          {ROLES.map((r) => (
            <button
              key={r.value}
              type="button"
              className={`${styles.tab} ${role === r.value ? styles.tabActive : ""}`}
              aria-pressed={role === r.value}
              onClick={() => update({ role: r.value })}
            >
              {r.label}
            </button>
          ))}
        </div>
        {onDetail && (
          <label>
            <span className="visually-hidden">段階</span>
            <select
              className={styles.select}
              value={stage ?? ""}
              onChange={(e) => update({ stage: e.target.value || null, tab: null })}
            >
              <option value="">段階: イベントの既定</option>
              {EVENT_STATUS_ORDER.map((s) => (
                <option key={s} value={s}>
                  {s} — {EVENT_STATUS[s].label}
                </option>
              ))}
            </select>
          </label>
        )}
        <span className={styles.toolbarHint}>画面の操作はこのブラウザの中だけで、再読み込みで元に戻ります</span>
      </div>
    </div>
  );
}
