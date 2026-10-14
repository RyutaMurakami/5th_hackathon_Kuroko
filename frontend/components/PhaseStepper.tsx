import type { ApiEventDetail } from "@/lib/api-types";
import { Icon } from "./Icon";
import styles from "./phase.module.css";

/** 画面の上に出す、全体の流れ（実演・体験のどちらでも）。いまの段階が分かるようにする */
const PHASES = [
  { no: 1, tag: "依頼", title: "チャットで依頼", text: "出欠と支払い委任を収集" },
  { no: 2, tag: "提案", title: "店舗の選定", text: "全員が帰りやすい店を提示（駅すぱあと）" },
  { no: 3, tag: "按分", title: "規程に沿った自動計算", text: "領収書読取・規程を適用" },
  { no: 4, tag: "承認", title: "承認・振込", text: "人が確認し銀行 API で実行（AP2・sunabar）" },
  { no: 5, tag: "完了", title: "明細確認・記憶", text: "入金確認と振り返りを保存" },
] as const;

/** イベントの状態が、どの段階にあたるか（1〜5）。開始前は 1 */
function phaseOf(status: ApiEventDetail["status"] | undefined): number {
  switch (status) {
    case "venue":
    case "booked":
      return 2;
    case "day_of":
    case "receipt":
    case "split":
      return 3;
    case "approval":
    case "payment":
      return 4;
    case "completed":
    case "retro":
    case "closed":
      return 5;
    default:
      return 1; // planning・rsvp・開始前
  }
}

export function PhaseStepper({ detail }: { detail: ApiEventDetail | null }) {
  const current = phaseOf(detail?.status);
  const finished = detail?.status === "closed";
  return (
    <ol className={styles.steps} aria-label="全体の流れ">
      {PHASES.map((p) => {
        const done = p.no < current || (finished && p.no === current);
        const now = p.no === current && !finished;
        return (
          <li
            key={p.no}
            className={`${styles.step} ${now ? styles.now : ""} ${done ? styles.done : ""}`}
            aria-current={now ? "step" : undefined}
          >
            <span className={styles.badge}>
              {done ? <Icon name="check" size="sm" /> : `${p.no}. `}
              {done ? ` ${p.tag}` : p.tag}
            </span>
            <span className={styles.title}>{p.title}</span>
            <span className={styles.text}>{p.text}</span>
          </li>
        );
      })}
    </ol>
  );
}
