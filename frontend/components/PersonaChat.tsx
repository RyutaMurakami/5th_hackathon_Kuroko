"use client";

// 登場人物（参加者・承認者）と KUROKO のチャット（SPEC 7.7）。Slack の DM に届くのと同じカードを出し、
// 体験用のイベントでは、ここからもボタンを押せる（押した結果は、Slack で押したときと同じ処理を通る）。
import { Fragment, useEffect, useId, useRef, useState } from "react";
import type { ApiPersona, ApiPersonaCard } from "@/lib/api-types";
import { Avatar, Button, Caption, Pill } from "./ui";
import event from "./event.module.css";
import styles from "./verify.module.css";

/** Slack の mrkdwn のうち、カードで使っているもの（太字・コード・改行）だけを描く */
function Mrkdwn({ text }: { text: string }) {
  return (
    <>
      {text.split("\n").map((line, i) => (
        <Fragment key={i}>
          {i > 0 && <br />}
          {line.split(/(\*[^*]+\*|`[^`]+`)/g).map((part, j) => {
            if (part.startsWith("*") && part.endsWith("*") && part.length > 2)
              return <strong key={j}>{part.slice(1, -1)}</strong>;
            if (part.startsWith("`") && part.endsWith("`") && part.length > 2)
              return <code key={j}>{part.slice(1, -1)}</code>;
            return <Fragment key={j}>{part}</Fragment>;
          })}
        </Fragment>
      ))}
    </>
  );
}

const WAITING: Record<ApiPersonaCard["kind"], string> = {
  consent: "出欠と委任の回答待ち",
  approval: "按分の承認待ち",
  budget: "予算超過の確認待ち",
  bank: "銀行での承認待ち",
  feedback: "振り返りの回答待ち",
};

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
  /** カードのボタン。終わるまで待てる Promise を返す */
  onPress?: (card: ApiPersonaCard, index: number) => Promise<unknown>;
  /** 体験用の「銀行で承認する」。承認できたら true を返す */
  onApproveBank?: () => Promise<boolean>;
  /** 銀行の承認ページに出す金額（この人の支払い） */
  bankAmountYen?: number | null;
  /** 実演用の画面: 届いたカードを見せるだけ（操作は、本人が Slack と銀行で行う） */
  readOnly?: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [bankOpen, setBankOpen] = useState(false);
  const open = persona.cards.filter((c) => c.buttons.length > 0);
  const press = async (card: ApiPersonaCard, index: number) => {
    if (card.bank) {
      setBankOpen(true); // 銀行の承認ページを模した画面を挟む（そこで「承認する」を押す）
      return;
    }
    setBusy(card.card_id);
    try {
      await onPress?.(card, index);
    } finally {
      setBusy(null);
    }
  };
  return (
    <section className={styles.column} aria-label={`${persona.display_name} と KUROKO のチャット`}>
      <header className={styles.columnHead}>
        <Avatar name={persona.display_name} />
        <div className={styles.columnWho}>
          <span className={styles.columnName}>{persona.display_name}</span>
          <Caption>
            {persona.job_title}・{role}
          </Caption>
        </div>
        {open.length > 0 ? <Pill tone="sun">{WAITING[open[0].kind]}</Pill> : <Pill tone="navy">対応なし</Pill>}
      </header>
      {/* この人が次にすること（いつも出す） */}
      <p className={`${styles.personaHint} ${open.length > 0 ? "" : styles.personaHintIdle}`}>
        {open.length === 0
          ? "いまは、対応することはありません。KUROKO から依頼が届くと、ここに出ます。"
          : readOnly
            ? `次にすること：${persona.display_name} が、${open[0].kind === "bank" ? "銀行（sunabar のサービスサイト）" : "Slack の DM "}で対応します（${WAITING[open[0].kind]}）。`
            : `次にすること：下のカードのボタンを押します（${WAITING[open[0].kind]}）。`}
      </p>
      <div className={styles.columnBody} aria-live="polite">
        <div className={`${event.message} ${event.fromKuroko} ${styles.personaCard}`}>
          <span className="visually-hidden">KUROKO：</span>
          <p className={styles.personaText}>
            {persona.display_name} さん、KUROKO です。飲み会の出欠・支払いの委任・承認などのお願いを、ここ（Slack の DM
            と同じ内容）にお送りします。
          </p>
          <span className={event.messageMeta}>KUROKO</span>
        </div>
        {persona.cards.map((card) => (
          <div key={card.card_id} className={`${event.message} ${event.fromKuroko} ${styles.personaCard}`}>
            <span className="visually-hidden">KUROKO：</span>
            {card.sections.map((s, i) => (
              <p key={i} className={styles.personaText}>
                <Mrkdwn text={s} />
              </p>
            ))}
            {card.buttons.length > 0 && !readOnly && (
              <div className={styles.formActions}>
                {card.buttons.map((b) => (
                  <Button
                    key={b.index}
                    variant={b.style === "primary" ? "primary" : "secondary"}
                    disabled={busy !== null || (!onPress && !card.bank) || (card.bank && !onApproveBank)}
                    onClick={() => void press(card, b.index)}
                  >
                    {busy === card.card_id ? "送信中…" : b.label}
                  </Button>
                ))}
              </div>
            )}
            {card.resolved_text && (
              <p className={styles.personaDone}>
                <Pill tone="lagoon">{card.kind === "bank" ? "完了" : "回答済み"}</Pill> {card.resolved_text}
              </p>
            )}
            <span className={event.messageMeta}>KUROKO</span>
          </div>
        ))}
      </div>
      <Caption>
        {readOnly
          ? "実演用の画面です。Slack に届いたカードを映しています。操作は、本人が Slack と銀行で行います。"
          : "Slack にも同じカードが届きます。どちらで押しても、同じ処理になります。"}
      </Caption>
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
