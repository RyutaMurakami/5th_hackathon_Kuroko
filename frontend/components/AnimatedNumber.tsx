"use client";

import { animate, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { DURATION, EASE_OUT } from "@/lib/motion";

/**
 * 前の値から新しい値へカウントアップする数字（DESIGN.md「Motion」）。
 * 最後は必ず渡された値そのもの。読み上げは最後の値だけ（途中の値は aria-hidden）。
 */
export function AnimatedNumber({ value, format = (n) => n.toLocaleString("ja-JP") }: {
  value: number;
  format?: (n: number) => string;
}) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(value);
  const from = useRef(value);

  useEffect(() => {
    if (reduce || from.current === value) {
      setShown(value);
      from.current = value;
      return;
    }
    const controls = animate(from.current, value, {
      duration: DURATION.slow,
      ease: EASE_OUT,
      onUpdate: (v) => setShown(Math.round(v)),
      onComplete: () => setShown(value),
    });
    from.current = value;
    return () => controls.stop();
  }, [value, reduce]);

  return (
    <>
      <span aria-hidden>{format(shown)}</span>
      <span className="visually-hidden">{format(value)}</span>
    </>
  );
}
