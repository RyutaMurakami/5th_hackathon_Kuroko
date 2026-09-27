"use client";

import { motion } from "motion/react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useDemoHref, useDemoRole } from "@/lib/demo";
import { defaultEventIdFor } from "@/lib/mock-data";
import { EASE_OUT } from "@/lib/motion";
import { ChatPanel } from "./ChatPanel";
import { useToast } from "./Toast";
import { Button, Card, Caption } from "./ui";
import detail from "./detail.module.css";
import styles from "./event.module.css";

// SPEC 7.6「体験できる流れ」
const HOW_TO = [
  "チャットで飲み会を依頼する（例: 来週金曜、チーム8人で軽く飲みに行きたい）",
  "KUROKOが整理した条件を確認して進める",
  "店舗の候補（過去の記憶に基づく理由つき）から1つ選ぶ",
  "予約画面のサンプルをダウンロードして、アップロードする",
  "開催後、領収書のサンプルをアップロードして金額を確定する",
  "按分の内訳を見る。承認・委任・銀行での承認は、デモ用の代行（架空の参加者・承認者）が Slack の代わりに行う",
  "送金の状況と、振り返り・KUROKOが覚えることを確かめる",
];

/** はじめる画面（`/`）。ログインの前はログインの選択、後は依頼のチャット */
export function StartView() {
  const router = useRouter();
  const role = useDemoRole();
  const href = useDemoHref();
  const { user, loading, signInWithGoogle } = useAuth();
  const { toast } = useToast();

  // 認証状態の確認中は、ログインボタンを一瞬出さない
  if (loading) return null;

  if (!user) {
    return (
      <main className={styles.page}>
        <Card>
          <div className={detail.hero}>
            <div className={styles.composer} style={{ gap: "var(--spacing-24)", padding: "var(--spacing-24) 0" }}>
              <h1 className={styles.pageTitle}>飲み会の幹事を、KUROKOに。</h1>
              <p>
                チャットで依頼すると、KUROKOが会社の規程に沿って、出欠・お店・按分・送金・振り返りまでを進めます。
                お金の権限に触れる操作（委任・承認）は、本人が Slack で行います。
              </p>
              <div className={styles.actions}>
                <Button
                  onClick={() =>
                    signInWithGoogle().catch((e: { code?: string }) => {
                      // ポップアップを閉じただけのときは何も出さない
                      if (e.code === "auth/popup-closed-by-user" || e.code === "auth/cancelled-popup-request") return;
                      toast({ tone: "coral", text: "ログインできませんでした。もう一度お試しください。" });
                    })
                  }
                >
                  Google でログイン
                </Button>
              </div>
              <Caption>
                幹事として登録されていない Google アカウントは、ゲストとして架空の会社「サンプル商事」のデータで体験できます（7日で削除されます）。
              </Caption>
            </div>
            <motion.div
              className={detail.heroImage}
              initial={{ opacity: 0, y: 16, rotate: -3 }}
              animate={{ opacity: 1, y: 0, rotate: 0 }}
              transition={{ duration: 0.6, ease: EASE_OUT }}
            >
              <Image src="/kuroko-icon.png" alt="KUROKO のアイコン（ビールを運ぶ黒子）" width={200} height={200} priority />
            </motion.div>
          </div>
        </Card>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <div>
        <h1 className={styles.pageTitle}>新しい飲み会を依頼する</h1>
        <p className={styles.pageMeta}>自然文で書いてください。足りないことは、KUROKOが質問します。</p>
      </div>
      <ChatPanel
        messages={[]}
        title="KUROKOに依頼する"
        autoFocus
        onSend={() =>
          // ダミー: 依頼を受けたイベント（企画中）へ移る。本番は send_message で Event が planning で作られる
          router.push(href(`/events/${defaultEventIdFor(role)}`, { stage: "planning" }))
        }
      />
      {role === "guest" && (
        <Card eyebrow="使い方" title="体験の流れ" id="how-to">
          <ol style={{ listStyle: "decimal", paddingLeft: "var(--spacing-24)" }}>
            {HOW_TO.map((step) => (
              <li key={step} style={{ padding: "var(--spacing-4) 0" }}>
                {step}
              </li>
            ))}
          </ol>
        </Card>
      )}
    </main>
  );
}
