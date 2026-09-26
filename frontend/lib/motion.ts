// 動きの値（DESIGN.md「Motion」）。CSS 側の --motion-* と同じ値を置く。
import type { Transition } from "motion/react";

export const DURATION = {
  fast: 0.15,
  base: 0.24,
  slow: 0.4,
} as const;

export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

/** KUROKO Panel の開閉、タブの選択中の塗りの移動、チェックの出現 */
export const SPRING: Transition = { type: "spring", stiffness: 380, damping: 36 };

export const FADE_UP: Transition = { duration: DURATION.base, ease: EASE_OUT };

/** 段階が進むときの、トースト → Flow Stepper → タブの中身 のずらし */
export const STAGGER = 0.12;

/** チャットの返事を流す速さ（1秒あたりの文字数） */
export const STREAM_CHARS_PER_SEC = 60;
