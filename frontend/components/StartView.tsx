"use client";

import { motion } from "motion/react";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { EASE_OUT } from "@/lib/motion";
import { useToast } from "./Toast";
import { Button, ButtonLink, Card, Caption } from "./ui";
import detail from "./detail.module.css";
import styles from "./event.module.css";

// SPEC 7.6「体験できる流れ」
const HOW_TO = [
  "入力の候補を押して、チャットで歓送迎会を依頼する。KUROKO が整理した計画を確かめて、確定する",
  "参加者（赤坂 くらお）と承認者（赤くら 花子）に届いたカードで、出欠と支払いの委任に答える（2人の代わりに、あなたが押せます）",
  "店の候補（選んだ理由と、過去の実績つき）から1つ選び、予約画面のサンプルをアップロードして確定する",
  "領収書のサンプルをアップロードして金額を確定する。決まった手順のコードが、規程に沿って按分する",
  "承認者として按分を承認し、参加者として銀行で振込を承認する（銀行は、承認ページを模した画面）",
  "入金の確認のあと、振り返りに答え、KUROKO が次回に覚える内容を確かめて保存する",
  "いつでも、チャットで規程のことを聞ける（KUROKO が規程の文書を調べて、条番号を添えて答えます）",
];

/** はじめる画面（`/`）。ログインの前はログインの選択、後は使い方と、チャットの画面への入口 */
export function StartView() {
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
                お金の権限に触れる操作（委任・承認）は、本人が Slack で行います（体験用の画面では、参加者・承認者のぶんも、この場で押して試せます）。
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
                幹事として登録されていない Google アカウントは、ゲストとして架空の会社「株式会社Akakura」のデータで体験できます（7日で削除されます）。
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
        <h1 className={styles.pageTitle}>KUROKO を体験する</h1>
        <p className={styles.pageMeta}>
          あなたが幹事になって、依頼から送金・振り返りまでを、1人で通して試せます。Slack や銀行の口座は要りません。
        </p>
      </div>
      <Card eyebrow="使い方" title="体験の流れ" id="how-to">
        <ol style={{ listStyle: "decimal", paddingLeft: "var(--spacing-24)" }}>
          {HOW_TO.map((step) => (
            <li key={step} style={{ padding: "var(--spacing-4) 0" }}>
              {step}
            </li>
          ))}
        </ol>
        <div className={styles.actions}>
          <ButtonLink href="/verify">体験をはじめる</ButtonLink>
          <ButtonLink href="/demo" variant="secondary">
            実演（開発者用）
          </ButtonLink>
        </div>
        <Caption>
          画面には、いつも「次にすること」が出ます。銀行は実験用の環境（sunabar）で、資金は仮想です。振込は実際に動き、sunabar のサービスサイトで確かめられます。入力した内容は7日で削除されます。実在の個人情報や領収書は入れないでください。
        </Caption>
      </Card>
    </main>
  );
}
