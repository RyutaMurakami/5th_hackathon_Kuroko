"use client";

// Demo Toolbar（DESIGN.md）用: 役割と段階を URL のクエリ（?role= &stage=）で持つ。
// バックエンドにつないだら、役割は Firebase の認証と API から決まる（ARCHITECTURE 4.5）。
import { usePathname, useSearchParams } from "next/navigation";
import { isEventStatus } from "./mock-data";
import type { EventStatus, Role } from "./types";

export const ROLES: { value: Role; label: string }[] = [
  { value: "organizer", label: "幹事" },
  { value: "guest", label: "ゲスト" },
];

export function parseRole(value: string | null | undefined): Role {
  return value === "guest" ? value : "organizer";
}

export function useDemoRole(): Role {
  return parseRole(useSearchParams().get("role"));
}

export function useDemoStage(): EventStatus | undefined {
  const stage = useSearchParams().get("stage");
  return isEventStatus(stage) ? stage : undefined;
}

/** 役割を引き継いだリンク先を作る（段階は画面ごとに違うので引き継がない） */
export function useDemoHref() {
  const role = useDemoRole();
  return (path: string, extra?: Record<string, string>) => {
    const params = new URLSearchParams({ role, ...extra });
    return `${path}?${params.toString()}`;
  };
}

export function useIsEventDetail(): boolean {
  return /^\/events\/[^/]+$/.test(usePathname());
}

export function isDemoToolbarEnabled(): boolean {
  return process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_DEMO_TOOLBAR === "true";
}
