"use client";

// 役割（幹事・ゲスト）は API が決める（許可リスト。SPEC 7.6）。取得できるまでは、権限の小さいゲストとして扱う。
import { createContext, useContext, useEffect, useState } from "react";
import { getMe } from "./api-client";
import { useAuth } from "./auth";
import { USE_API } from "./data-source";
import type { Role } from "./types";

const RoleContext = createContext<Role>("guest");

export function ApiRoleProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [role, setRole] = useState<Role>("guest");
  useEffect(() => {
    if (!USE_API || !user) return;
    let alive = true;
    getMe().then(
      (me) => alive && setRole(me.role),
      () => alive && setRole("guest"),
    );
    return () => {
      alive = false;
    };
  }, [user]);
  return <RoleContext.Provider value={role}>{children}</RoleContext.Provider>;
}

export function useApiRole(): Role {
  return useContext(RoleContext);
}
