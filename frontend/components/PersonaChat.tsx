"use client";

// 登場人物（参加者・承認者）と KUROKO のチャット（SPEC 7.7）。Slack の DM に届くのと同じカードを出し、
// 体験用のイベントでは、ここからもボタンを押せる（押した結果は、Slack で押したときと同じ処理を通る）。
import { Fragment, useState } from "react";
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
};

export function PersonaChat({
  persona,
  role,
  onPress,
  onApproveBank,
}: {
  persona: ApiPersona;
  /** 列の見出しに添える役割（例: 参加者／承認者） */
  role: string;
  /** カードのボタン。終わるまで待てる Promise を返す */
  onPress?: (card: ApiPersonaCard, index: number) => Promise<unknown>;
  onApproveBank?: () => Promise<unknown>;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const open = persona.cards.filter((c) => c.buttons.length > 0);
  const press = async (card: ApiPersonaCard, index: number) => {
    setBusy(card.card_id);
    try {
      await (card.bank ? onApproveBank?.() : onPress?.(card, index));
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
      <div className={styles.columnBody} aria-live="polite">
        {persona.cards.length === 0 && (
          <Caption>
            まだ、KUROKO からの連絡はありません。幹事が計画を確定すると、ここに出欠と委任の依頼が届きます。
          </Caption>
        )}
        {persona.cards.map((card) => (
          <div key={card.card_id} className={`${event.message} ${event.fromKuroko} ${styles.personaCard}`}>
            <span className="visually-hidden">KUROKO：</span>
            {card.sections.map((s, i) => (
              <p key={i} className={styles.personaText}>
                <Mrkdwn text={s} />
              </p>
            ))}
            {card.buttons.length > 0 && (
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
            {card.resolved_text && card.kind !== "bank" && (
              <p className={styles.personaDone}>
                <Pill tone="lagoon">回答済み</Pill> {card.resolved_text}
              </p>
            )}
            <span className={event.messageMeta}>KUROKO</span>
          </div>
        ))}
      </div>
      <Caption>Slack にも同じカードが届きます。どちらで押しても、同じ処理になります。</Caption>
    </section>
  );
}
