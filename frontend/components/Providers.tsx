"use client";

import { MotionConfig } from "motion/react";
import { ToastProvider } from "./Toast";

/** 画面全体で使う状態と動きの設定。reducedMotion="user" で OS の「視差効果を減らす」に従う */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <ToastProvider>{children}</ToastProvider>
    </MotionConfig>
  );
}
