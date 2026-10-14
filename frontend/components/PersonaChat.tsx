"use client";

// 登場人物（参加者・承認者）と KUROKO のチャット（SPEC 7.7）。Slack の DM に届くのと同じカードを出し、
// 体験用のイベントでは、ここからもボタンを押せる（押した結果は、Slack で押したときと同じ処理を通る）。
import { useEffect, useId, useRef, useState } from "react";
import type { ApiPersona, ApiPersonaCard } from "@/lib/api-types";
import { ChatAvatar, KurokoRow, Mrkdwn, Thread, chatStyles as chat } from "./ChatThread";
import { Button, Caption, Pill } from "./ui";
import styles from "./verify.module.css";

const WAITING: Record<ApiPersonaCard["kind"], string> = {
  consent: "出欠と委任の回答待ち",
  approval: "按分の承認待ち",
  budget: "予算超過の確認待ち",
  bank: "銀行での承認待ち",
  feedback: "振り返りの回答待ち",
  notice: "お知らせ",
};

export type CardInputs = { station?: string; dislikes?: string };

/**
 * 銀行の承認ページを模した画面（体験用。SPEC 7.7）。
 * 本物では、銀行のサービスサイトにログインし、取引パスワードで承認する。ここでは、その手順を省き、
 * 承認の結果（成功）だけを見せる。押したときに起きる処理は、Slack のボタンと同じ。
 */
function BankApprovalDialog({
  payer,
  amountYen,
  onApprove,
  onClose,
}: {
  payer: string;
  amountYen: number | null;
  /** 承認できたら true */
  onApprove: () => Promise<boolean>;
  onClose: () => void;
}) {
  const [phase, setPhase] = useState<"confirm" | "sending" | "done" | "failed">("confirm");
  const titleId = useId();
  const main = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    main.current?.focus();
  }, [phase]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && phase !== "sending") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, phase]);
  const approve = async () => {
    setPhase("sending");
    setPhase((await onApprove()) ? "done" : "failed");
  };
  return (
    <div className={styles.bankOverlay}>
      <div className={styles.bankPage} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className={styles.bankHead}>
          <span>サンプル銀行　サービスサイト</span>
          <Pill tone="sun">体験用の画面</Pill>
        </div>
        <div className={styles.bankBody}>
          <h2 id={titleId} className={styles.bankTitle}>
            {phase === "done" ? "振込の承認が完了しました" : "振込の承認"}
          </h2>
          <dl className={styles.bankRows}>
            <dt>振込を依頼した人</dt>
            <dd>{payer}（あなたの支払いエージェントが、委任の範囲内で依頼）</dd>
            <dt>振込先</dt>
            <dd>幹事の口座</dd>
            <dt>金額</dt>
            <dd>{amountYen !== null ? `${amountYen.toLocaleString()}円` : "カードに記載の金額"}</dd>
          </dl>
          {phase === "done" ? (
            <p className={styles.bankDone} aria-live="polite">
              <span aria-hidden="true">✓</span>
              承認を受け付け、振込を実行しました。1〜2分で、KUROKO が入金を明細で確認します。
            </p>
          ) : (
            <p className={styles.bankNote}>
              本物の銀行では、サービスサイトにログインし、取引パスワードを入力して承認します。体験用のため、
              ログインとパスワードの入力は省いています（銀行は実験用の環境で、資金は仮想です）。
            </p>
          )}
          {phase === "failed" && (
            <p className={styles.bankNote} role="alert">
              承認できませんでした。すでに承認済みか、振込の依頼がまだ届いていません。
            </p>
          )}
          <div className={styles.formActions}>
            {phase === "done" || phase === "failed" ? (
              <Button ref={main} onClick={onClose}>
                閉じる
              </Button>
            ) : (
              <>
                <Button ref={main} disabled={phase === "sending"} onClick={() => void approve()}>
                  {phase === "sending" ? "承認しています…" : "承認する"}
                </Button>
                <Button variant="secondary" disabled={phase === "sending"} onClick={onClose}>
                  キャンセル
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function PersonaChat({
  persona,
  role,
  onPress,
  onApproveBank,
  bankAmountYen = null,
  readOnly = false,
}: {
  persona: ApiPersona;
  /** 列の見出しに添える役割（例: 参加者／承認者） */
  role: string;
  /** カードのボタン。終わるまで待てる Promise を返す。`inputs` は、出欠のカードの入力欄 */
  onPress?: (card: ApiPersonaCard, index: number, inputs?: CardInputs) => Promise<unknown>;
  /** 体験用の「銀行で承認する」。承認できたら true を返す */
  onApproveBank?: () => Promise<boolean>;
  /** 銀行の承認ページに出す金額（この人の支払い） */
  bankAmountYen?: number | null;
  /** 実演用の画面: 届いたカードを見せるだけ（操作は、本人が Slack と銀行で行う） */
  readOnly?: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [bankOpen, setBankOpen] = useState(false);
  // 出欠のカードの入力欄（開催希望駅・苦手な食べ物）。はじめは、サーバーが出したデモ用の候補
  const [typed, setTyped] = useState<Record<string, string>>({});
  const open = persona.cards.filter((c) => c.buttons.length > 0);
  const valueOf = (card: ApiPersonaCard, key: string) =>
    typed[`${card.card_id}:${key}`] ?? card.fields?.find((f) => f.key === key)?.value ?? "";
  const press = async (card: ApiPersonaCard, index: number) => {
    if (card.bank) {
      setBankOpen(true); // 銀行の承認ページを模した画面を挟む（そこで「承認する」を押す）
      return;
    }
    setBusy(`${card.card_id}:${index}`);
    try {
      const inputs = card.fields?.length
        ? { station: valueOf(card, "station"), dislikes: valueOf(card, "dislikes") }
        : undefined;
      await onPress?.(card, index, inputs);
    } finally {
      setBusy(null);
    }
  };
  return (
    <section className={chat.dm} aria-label={`${persona.display_name} と KUROKO のチャット`}>
      <header className={chat.dmHead}>
        <ChatAvatar who={persona.user_id} name={persona.display_name} />
        <div className={chat.dmWho}>
          <span className={chat.dmName}>{persona.display_name}</span>
          <Caption>
            {persona.job_title}・{role}（KUROKO との DM）
          </Caption>
        </div>
        {open.length > 0 ? <Pill tone="sun">{WAITING[open[0].kind]}</Pill> : <Pill tone="navy">対応なし</Pill>}
      </header>
      {/* この人が次にすること（いつも出す） */}
      <p className={`${chat.dmNote} ${open.length > 0 ? "" : chat.dmNoteIdle}`}>
        {open.length === 0
          ? "いまは、対応することはありません。KUROKO から依頼が届くと、ここに出ます。"
          : readOnly
            ? `次にすること：${persona.display_name} が、${open[0].kind === "bank" ? "銀行（sunabar のサービスサイト）" : "Slack の DM "}で対応します（${WAITING[open[0].kind]}）。`
            : `次にすること：下のカードのボタンを押します（${WAITING[open[0].kind]}）。`}
      </p>
      <Thread
        label={`${persona.display_name} に届いたメッセージ`}
        follow={persona.cards.map((c) => `${c.card_id}:${c.resolved_text ? 1 : 0}`).join(",")}
      >
        <KurokoRow>
          {persona.display_name} さん、KUROKO です。飲み会の出欠・支払いの委任・承認などのお願いを、ここ（Slack の DM
          と同じ内容）にお送りします。
        </KurokoRow>
        {persona.cards.map((card) => (
          <KurokoRow key={card.card_id} at={card.created_at || null} card>
            {card.sections.map((s, i) => (
              <p key={i} className={styles.personaText}>
                <Mrkdwn text={s} />
              </p>
            ))}
            {!readOnly && card.fields && card.fields.length > 0 && (
              <div className={chat.form}>
                <span className={`${chat.wide} ${chat.cardTitle}`}>お店選びのために、教えてください</span>
                {card.fields.map((f) => (
                  <label key={f.key} className={`${chat.field} ${chat.wide}`}>
                    {f.label}
                    <input
                      type="text"
                      value={valueOf(card, f.key)}
                      placeholder={f.placeholder}
                      maxLength={f.key === "station" ? 40 : 200}
                      onChange={(e) => setTyped((p) => ({ ...p, [`${card.card_id}:${f.key}`]: e.target.value }))}
                    />
                  </label>
                ))}
                <Caption className={chat.wide}>
                  全員が帰りやすく、食べられるお店を探すのに使います。駅は駅コード、食べ物は決まった語彙に変換して
                  持ち、書いた文そのものは保存しません（開催の完了後に削除します）。
                </Caption>
              </div>
            )}
            {card.buttons.length > 0 && !readOnly && (
              <div className={chat.actions}>
                {card.buttons.map((b) => (
                  <Button
                    key={b.index}
                    variant={b.style === "primary" ? "primary" : "secondary"}
                    disabled={busy !== null || (!onPress && !card.bank) || (card.bank && !onApproveBank)}
                    onClick={() => void press(card, b.index)}
                  >
                    {busy === `${card.card_id}:${b.index}` ? "送信中…" : b.label}
                  </Button>
                ))}
              </div>
            )}
            {card.resolved_text && (
              <p className={styles.personaDone}>
                <Pill tone="lagoon">{card.kind === "bank" ? "完了" : "回答済み"}</Pill> {card.resolved_text}
              </p>
            )}
          </KurokoRow>
        ))}
      </Thread>
      <div className={chat.dmFoot}>
        <Caption>
          {readOnly
            ? "実演用の画面です。Slack に届いたカードを映しています。操作は、本人が Slack と銀行で行います。"
            : "Slack の DM にも同じカードが届きます。どちらで押しても、同じ処理になります。"}
        </Caption>
      </div>
      {bankOpen && onApproveBank && (
        <BankApprovalDialog
          payer={persona.display_name}
          amountYen={bankAmountYen}
          onApprove={onApproveBank}
          onClose={() => setBankOpen(false)}
        />
      )}
    </section>
  );
}
