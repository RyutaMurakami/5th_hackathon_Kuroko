"use client";

// Firebase Auth（Google ログインだけ。匿名認証は使わない。SPEC 7.6、TASKS F4）。
// 役割（幹事・ゲスト）の判定は、許可リスト（P6）と Web 向け API（B14）ができてから API で行う。
// それまでは Demo のクエリ（lib/demo.ts）のまま。
import {
  type Auth,
  type User,
  GoogleAuthProvider,
  connectAuthEmulator,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
} from "firebase/auth";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getFirebaseApp } from "./firebase";

type AuthState = {
  user: User | null;
  /** 最初の認証状態の確認が終わるまで true */
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

let authInstance: Auth | undefined;

function getFirebaseAuth(): Auth {
  if (!authInstance) {
    authInstance = getAuth(getFirebaseApp());
    if (process.env.NEXT_PUBLIC_FIREBASE_EMULATOR === "true") {
      connectAuthEmulator(authInstance, "http://127.0.0.1:9099", { disableWarnings: true });
    }
  }
  return authInstance;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(
    () =>
      onAuthStateChanged(getFirebaseAuth(), (next) => {
        setUser(next);
        setLoading(false);
      }),
    [],
  );

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      signInWithGoogle: async () => {
        const provider = new GoogleAuthProvider();
        provider.setCustomParameters({ prompt: "select_account" });
        await signInWithPopup(getFirebaseAuth(), provider);
      },
      signOut: () => firebaseSignOut(getFirebaseAuth()),
    }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
