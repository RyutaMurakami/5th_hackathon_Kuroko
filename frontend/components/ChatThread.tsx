"use client";

// DM のように見せるチャットの部品（DESIGN.md「DM Board」。SPEC 7.7）。
// 相手（KUROKO）の発言は、左にアイコン・上に名前と時刻。自分の発言は、右に寄せる。
// 表示だけを持ち、状態は呼び出し側（VerifyView・PersonaChat）が持つ。
import Image from "next/image";
import { Fragment, useEffect, useRef, useState } from "react";
import { formatTime, initialOf } from "@/lib/format";
import { Icon } from "./Icon";
import event from "./event.module.css";
import styles from "./chat.module.css";

/** アイコンの画像（`public/avatars`）。無い人は、頭文字を出す */
const AVATARS: Record<string, string> = {
  kuroko: "/avatars/kuroko.png",
  kurao: "/avatars/kurao.jpg",
  hanako: "/avatars/hanako.jpg",
};

export function ChatAvatar({ who, name }: { who: string; name: string }) {
  const src = AVATARS[who];
  if (!src) {
    return (
      <span className={`${styles.avatar} ${styles.avatarInitial}`} aria-hidden>
        {initialOf(name)}
      </span>
    );
  }
  // 小さな静的画像なので、最適化のサーバー処理は通さない
  return <Image className={styles.avatar} src={src} alt="" width={40} height={40} unoptimized />;
}

/** KUROKO からの発言。`card` は、入力欄・ボタンを持つ発言（横幅いっぱいに取る） */
export function KurokoRow({
  at,
  card = false,
  children,
}: {
  at?: string | null;
  card?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={styles.row}>
      <ChatAvatar who="kuroko" name="KUROKO" />
      <div className={styles.rowBody}>
        <div className={styles.rowHead}>
          <span className={styles.name}>KUROKO</span>
          <span className={styles.app}>アプリ</span>
          {at && <span className={styles.time}>{formatTime(at)}</span>}
        </div>
        <div className={`${styles.bubble} ${card ? styles.card : ""}`}>{children}</div>
      </div>
    </div>
  );
}

/** 自分（その列の持ち主）の発言。右に寄せる */
export function MineRow({ at, note, children }: { at?: string | null; note?: string; children: React.ReactNode }) {
  return (
    <div className={styles.mine}>
      {children}
      {(at || note) && (
        <span className={styles.time}>
          {note}
          {note && at ? "・" : ""}
          {at ? formatTime(at) : ""}
        </span>
      )}
    </div>
  );
}

export function MineBubble({ children }: { children: React.ReactNode }) {
  return <div className={`${styles.bubble} ${styles.bubbleMine}`}>{children}</div>;
}

/** 送った画像。手元に画像が残っていなければ（読み直したあと）、ファイルの札を出す */
export function MinePhoto({ url, label }: { url: string | null; label: string }) {
  if (!url) {
    return (
      <MineBubble>
        <span className={styles.fileChip}>
          <Icon name="image" size="sm" />
          {label}
        </span>
      </MineBubble>
    );
  }
  // 利用者が選んだ手元の画像（blob URL）。next/image は使えない
  // eslint-disable-next-line @next/next/no-img-element
  return <img className={styles.photo} src={url} alt={label} />;
}

/** KUROKO が処理している途中（考え中・読み取り中・店を探している、など） */
export function KurokoWorking({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <KurokoRow>
      <span className={styles.typing} role="status">
        <span className={event.thinkingDots} aria-hidden>
          <span />
          <span />
          <span />
        </span>
        <span>
          {children}
          <Elapsed hint={hint} />
        </span>
      </span>
    </KurokoRow>
  );
}

const SLOW_AFTER_SEC = 8;

/** 待っている秒数。長くなったら、時間がかかる理由を添える */
function Elapsed({ hint }: { hint?: string }) {
  const [sec, setSec] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSec((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  if (sec < 3) return null;
  return (
    <span aria-hidden>
      （{sec}秒）{sec >= SLOW_AFTER_SEC && hint ? ` ${hint}` : ""}
    </span>
  );
}

/**
 * 発言の流れ。**この中だけをスクロールする**（ページ全体は動かさない）。
 * `follow` が変わったら（発言・カードが増えたら）、最後まで送る。
 */
export function Thread({
  label,
  follow,
  children,
}: {
  label: string;
  follow: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // 開いたとき・大きく離れているときは、すぐに最後へ。少し増えただけなら、なめらかに送る
    const far = el.scrollHeight - el.scrollTop - el.clientHeight > el.clientHeight;
    el.scrollTo({ top: el.scrollHeight, behavior: first.current || far ? "auto" : "smooth" });
    first.current = false;
  }, [follow]);
  return (
    <div className={styles.thread} ref={ref} role="log" aria-label={label} aria-live="polite" tabIndex={0}>
      {children}
    </div>
  );
}

/** Slack の mrkdwn のうち、カードで使っているもの（太字・コード・リンク・改行）だけを描く */
export function Mrkdwn({ text }: { text: string }) {
  return (
    <>
      {text.split("\n").map((line, i) => (
        <Fragment key={i}>
          {i > 0 && <br />}
          {line.split(/(\*[^*]+\*|`[^`]+`|<https:\/\/[^|>]+\|[^>]+>)/g).map((part, j) => {
            if (part.startsWith("*") && part.endsWith("*") && part.length > 2)
              return <strong key={j}>{part.slice(1, -1)}</strong>;
            if (part.startsWith("`") && part.endsWith("`") && part.length > 2)
              return <code key={j}>{part.slice(1, -1)}</code>;
            const link = /^<(https:\/\/[^|>]+)\|([^>]+)>$/.exec(part);
            if (link)
              return (
                <a key={j} className={styles.inlineLink} href={link[1]} target="_blank" rel="noreferrer">
                  {link[2]}
                </a>
              );
            return <Fragment key={j}>{part}</Fragment>;
          })}
        </Fragment>
      ))}
    </>
  );
}

export { styles as chatStyles };
