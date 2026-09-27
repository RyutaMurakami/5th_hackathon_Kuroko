"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

/** ログインしていなければ、はじめる画面（`/`。ログインの入口）へ戻す。`/` 自体は誰でも開ける */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const guarded = pathname !== "/";

  useEffect(() => {
    if (guarded && !loading && !user) router.replace("/");
  }, [guarded, loading, user, router]);

  if (guarded && (loading || !user)) return null;
  return <>{children}</>;
}
