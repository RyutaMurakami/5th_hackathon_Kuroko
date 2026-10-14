"use client";

// KUROKO とのチャットの画面。幹事・参加者・承認者の3人ぶんの DM を、最初から並べて出す（SPEC 7.7）。
// 画面は2つあり、作りは同じで、参加者・承認者の操作の場所だけが違う:
// - 体験用（/verify。審査員）: 2人の列のカードを、この画面から押せる。銀行は、承認ページを模した画面
// - 実演用（/demo。開発者）: 2人は Slack と本物の銀行（sunabar）で操作する。列は、届いたカードを映すだけ
// 幹事の入力（計画・店・予約・領収書・振り返り）は、チャットの流れの中の、KUROKO からのカードで完結する
// （SPEC 7.5）。予約の画面・領収書は、チャットに画像を送って渡す。
// **ページ全体は動かさず、各チャットの中だけをスクロールする**（globals.css の data-chat-page）。
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  approveBank,
  errorText,
  getEvent,
  getMe,
  listEvents,
  pressPersonaCard,
  resetScenario,
  sendMessage,
  uploadFile,
} from "@/lib/api-client";
import type { ApiEventDetail, ApiEventSummary, ApiMe, ApiPersona, ApiUiMode } from "@/lib/api-types";
import { useAuth } from "@/lib/auth";
import {
  ChatAvatar,
  KurokoRow,
  KurokoWorking,
  MineBubble,
  MinePhoto,
  MineRow,
  Thread,
  chatStyles as styles,
} from "./ChatThread";
import { Icon } from "./Icon";
import { PersonaChat } from "./PersonaChat";
import { PhaseStepper } from "./PhaseStepper";
import { ScenarioHint } from "./ScenarioHint";
import {
  type AnchorKind,
  AnchoredCard,
  type ImageKind,
  StepForms,
  anchorsAvailable,
  expectedImage,
} from "./StepForms";
import { Button, Caption, ErrorBanner, InfoBanner, Pill } from "./ui";

const POLL_MS = 5000;
const POLL_BUSY_MS = 2000; // 返答・店の検索・按分を待っているあいだは、短い間隔で読み直す
const SPLIT_WAIT_MAX_MS = 60_000; // 按分の結果を待つ上限（これを過ぎたら、待ち表示をやめる）
const ACCEPT = ["image/jpeg", "image/png", "application/pdf"];
const MAX_BYTES = 5 * 1024 * 1024; // 画面でも検査するが、正は API 側（SPEC 7.5）
const SAMPLE: Record<ImageKind, { url: string; name: string; type: string }> = {
  reservation: { url: "/samples/reservation_sample.png", name: "reservation_sample.png", type: "image/png" },
  receipt: { url: "/samples/receipt_sample.jpg", name: "receipt_sample.jpg", type: "image/jpeg" },
};
const IMAGE_LABEL: Record<ImageKind, string> = { reservation: "予約の画面", receipt: "領収書" };

// 計画を確定するまでは、参加者がまだ決まっていない。列は最初から開いておく（名簿は kuroko-api が持つ）
const PLACEHOLDER_PERSONAS: ApiPersona[] = [
  { user_id: "hanako", display_name: "赤くら 花子", job_title: "部長", cards: [] },
  { user_id: "kurao", display_name: "赤坂 くらお", job_title: "一般", cards: [] },
];

const STATUS_LABEL: Record<string, string> = {
  planning: "計画", rsvp: "出欠", venue: "店", booked: "予約済み", day_of: "当日", receipt: "領収書",
  split: "按分", approval: "承認", payment: "振込", completed: "完了", retro: "振り返り", closed: "終了",
};

const COPY: Record<ApiUiMode, { title: string; meta: string; banner: string }> = {
  experience: {
    title: "KUROKO を体験する",
    meta: "あなたが幹事です。右の2人（参加者・承認者）の対応も、この画面で進められます",
    banner:
      "左が、幹事（あなた）と KUROKO の DM です。右の2列は、参加者（赤坂 くらお）と承認者（赤くら 花子）に届く KUROKO からの DM で、Slack に届くものと同じです。体験用に、ここから2人の代わりにボタンを押せます。銀行の承認は、承認ページを模した画面で行い、お金は動きません。",
  },
  live: {
    title: "実演（開発者用）",
    meta: "参加者・承認者は Slack で操作し、振込は本物の銀行 API（sunabar）で実行します",
    banner:
      "開発者用の画面です。ここで作ったイベントは、赤坂 くらお・赤くら 花子の振込を、本物の銀行 API（sunabar。資金は仮想）に依頼します。2人は、Slack の DM と sunabar のサービスサイトで操作します。右の2列は、届いたカードを映すだけです。",
  },
};

/** チャットに送った画像（手元の表示用。読み直すと、画像そのものは残らない） */
type SentImage = {
  key: string;
  kind: ImageKind;
  url: string | null;
  at: string;
  state: "sending" | "sent" | "failed";
  uploadId?: string;
};

type Item =
  | { type: "text"; key: string; at: string; mine: boolean; text: string; card: AnchorKind | null }
  | { type: "image"; key: string; at: string; kind: ImageKind; url: string | null; sending: boolean };

/** 発言と、送った画像を、時刻の順に並べる */
function timeline(detail: ApiEventDetail | null, sent: SentImage[]): Item[] {
  if (!detail) return [];
  const local = new Map(sent.filter((s) => s.uploadId).map((s) => [s.uploadId, s]));
  const items: Item[] = [
    // 返答を作っているあいだのメッセージ（本文は空）は、一覧に出さない。「考え中」で見せる
    ...detail.messages
      .filter((m) => m.status !== "pending" && m.role !== "system")
      .map(
        (m): Item => ({
          type: "text", key: m.message_id, at: m.created_at, mine: m.role === "organizer", text: m.text,
          card: m.card ?? null,
        }),
      ),
    ...detail.uploads
      .filter((u) => u.status === "registered")
      .map(
        (u): Item => ({
          type: "image", key: u.upload_id, at: u.created_at, kind: u.kind,
          url: local.get(u.upload_id)?.url ?? null, sending: false,
        }),
      ),
  ];
  items.sort((a, b) => a.at.localeCompare(b.at));
  // 送っている途中の画像（まだサーバーの一覧に無い）は、最後に出す
  const known = new Set(detail.uploads.filter((u) => u.status === "registered").map((u) => u.upload_id));
  for (const s of sent) {
    if (s.state === "sending" || (s.state === "sent" && s.uploadId && !known.has(s.uploadId))) {
      items.push({ type: "image", key: s.key, at: s.at, kind: s.kind, url: s.url, sending: s.state === "sending" });
    }
  }
  return items;
}

export function VerifyView({ mode = "experience" }: { mode?: ApiUiMode }) {
  const { user } = useAuth();
  const [me, setMe] = useState<ApiMe | null>(null);
  const [events, setEvents] = useState<ApiEventSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApiEventDetail | null>(null);
  const [sending, setSending] = useState(false);
  const [outgoing, setOutgoing] = useState<string | null>(null); // 送った直後の発言（一覧に載るまで）
  const [images, setImages] = useState<SentImage[]>([]);
  const [computing, setComputing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const live = mode === "live";
  const copy = COPY[mode];
  // 返答は、別に作られる（Hosting の60秒制限を避けるため。SPEC 7.5）。できるまで「考え中」を出す
  const replyPending = detail?.messages.some((m) => m.status === "pending") ?? false;
  const thinking = sending || replyPending;
  const imageBusy = images.some((i) => i.state === "sending");
  const searching = detail?.status === "venue" && detail.venue_search?.status === "searching";
  const waiting = replyPending || searching || detail?.status === "split" || detail?.status === "completed";

  const run = useCallback(async (fn: () => Promise<unknown>, done?: string) => {
    setError(null);
    setNotice(null);
    try {
      await fn();
      if (done) setNotice(done);
      return true;
    } catch (e) {
      setError(errorText(e));
      return false;
    }
  }, []);

  const refresh = useCallback(
    async (id: string | null) => {
      setEvents(await listEvents(mode));
      if (id) setDetail(await getEvent(id));
    },
    [mode],
  );

  useEffect(() => {
    if (!user) return;
    void run(async () => {
      setMe(await getMe());
      await refresh(selected);
    });
  }, [user, selected, refresh, run]);

  // 参加者・承認者の操作や、銀行の承認で状態が進むので、一定の間隔で読み直す
  useEffect(() => {
    if (!user || !selected) return;
    const t = setInterval(() => void refresh(selected).catch(() => undefined), waiting ? POLL_BUSY_MS : POLL_MS);
    return () => clearInterval(t);
  }, [user, selected, refresh, waiting]);

  // 実演用: Slack の DM から依頼が始まったとき（新しいイベントが現れたとき）、その画面を開く
  const knownIds = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!user || !live || selected) return;
    const t = setInterval(() => void refresh(null).catch(() => undefined), POLL_MS);
    return () => clearInterval(t);
  }, [user, live, selected, refresh]);
  useEffect(() => {
    if (!live) return;
    if (knownIds.current === null) {
      if (events.length > 0 || me) knownIds.current = new Set(events.map((e) => e.event_id));
      return;
    }
    const fresh = events.find((e) => !knownIds.current?.has(e.event_id));
    events.forEach((e) => knownIds.current?.add(e.event_id));
    if (fresh && !selected && !thinking) setSelected(fresh.event_id);
  }, [events, live, me, selected, thinking]);

  // 按分の結果が出るまで、計算の途中経過を見せる（結果が出たら、内訳に置き換わる）
  useEffect(() => {
    if (!computing) return;
    if (detail?.split) {
      setComputing(false);
      return;
    }
    const t = setTimeout(() => setComputing(false), SPLIT_WAIT_MAX_MS);
    return () => clearTimeout(t);
  }, [computing, detail?.split]);

  const blocked = live && me !== null && !me.live_allowed; // 実演用は、登録した開発者のアカウントだけ
  const personas: ApiPersona[] = detail?.personas?.length ? detail.personas : PLACEHOLDER_PERSONAS;
  const approverId = detail?.split?.approval.approver_user_id ?? "hanako";
  const hint = detail?.hint ?? me?.start_hints[mode] ?? null;
  const chats = hint?.example?.chats;
  const suggestions = Array.isArray(chats) ? chats.filter((c): c is string => typeof c === "string") : [];
  const items = timeline(detail, images);
  // 状態つきのカード（店の候補・按分の内訳・振込の依頼・振り返り）は、同じ種類のうち、いちばん
  // 新しい発言の位置に出す（あとの発言が、カードより上に並んで、時系列が崩れないように）
  const available = detail ? anchorsAvailable(detail) : [];
  const anchorAt = new Map<AnchorKind, string>();
  for (const item of items) {
    if (item.type === "text" && item.card && available.includes(item.card)) anchorAt.set(item.card, item.key);
  }
  const anchored = new Set(anchorAt.keys());
  const lastMine = [...items].reverse().find((i) => i.type === "text" && i.mine);
  const showOutgoing = !!outgoing && thinking && !(lastMine?.type === "text" && lastMine.text === outgoing);
  const imageKind = expectedImage(detail);
  const done = detail?.status === "closed";
  // 実演用は、幹事の操作を Slack の DM で行う（SPEC 7.8）。この画面は、進み具合を映すだけ
  const viewOnly = live && !!detail;

  const select = (id: string | null) => {
    setSelected(id);
    if (!id) setDetail(null);
    setImages([]);
    setOutgoing(null);
    setComputing(false);
    setError(null);
    setNotice(null);
  };

  const send = async () => {
    const text = draft.trim();
    if (!text || thinking || blocked) return;
    setDraft("");
    setOutgoing(text);
    setSending(true);
    await run(async () => {
      const out = await sendMessage(text, selected ?? undefined, mode);
      setSelected(out.event_id);
      await refresh(out.event_id);
    });
    setSending(false);
  };

  /** 画像を、チャットに送る（予約の画面・領収書。どちらとして受け取るかは、いまの段階で決まる） */
  const sendImage = async (file: File) => {
    if (!detail || !imageKind) {
      setError(errorText(new ApiError(409, "image_not_expected")));
      return;
    }
    if (!ACCEPT.includes(file.type)) return setError(errorText(new ApiError(400, "unsupported_type")));
    if (file.size > MAX_BYTES) return setError(errorText(new ApiError(400, "invalid_size")));
    const key = `local-${Date.now()}`;
    const url = file.type.startsWith("image/") ? URL.createObjectURL(file) : null;
    const patch = (next: Partial<SentImage>) =>
      setImages((list) => list.map((i) => (i.key === key ? { ...i, ...next } : i)));
    setImages((list) => [...list, { key, kind: imageKind, url, at: new Date().toISOString(), state: "sending" }]);
    const ok = await run(async () => {
      const out = await uploadFile(detail.event_id, imageKind, file);
      patch({ uploadId: out.upload_id });
      await refresh(detail.event_id);
    });
    patch({ state: ok ? "sent" : "failed" });
  };

  const sendSample = async (kind: ImageKind) => {
    const sample = SAMPLE[kind];
    let blob: Blob;
    try {
      const res = await fetch(sample.url);
      if (!res.ok) throw new Error("not found");
      blob = await res.blob();
    } catch {
      setError("サンプルの画像を読み込めませんでした。");
      return;
    }
    await sendImage(new File([blob], sample.name, { type: sample.type }));
  };

  /** この画面で作ったイベントをすべて消し、シナリオを最初から始める（SPEC 7.7） */
  const clear = async () => {
    if (!window.confirm("この画面で作ったイベントと通知をすべて削除して、最初からやり直します。よろしいですか？")) {
      return;
    }
    const ok = await run(async () => {
      await resetScenario(mode);
      select(null);
      await refresh(null);
    });
    if (ok) setNotice("クリアしました。最初から始められます。");
  };

  const follow = [
    items.length, thinking, showOutgoing, imageBusy, computing, detail?.status, detail?.venue_candidates.length,
    detail?.venue_search?.status, detail?.venue?.place_id, detail?.uploads.length, detail?.retro?.status,
    detail?.split?.approval.status,
  ].join("|");

  return (
    <main className={styles.page} data-chat-page>
      <div className={styles.head}>
        <h1 className={styles.title}>{copy.title}</h1>
        <p className={styles.headMeta}>{copy.meta}</p>
        {done && <Pill tone="lagoon">デモ完了</Pill>}
        <Pill tone={live ? "sun" : "navy"}>{live ? "実演用：本物の銀行 API" : "体験用：お金は動きません"}</Pill>
      </div>

      <div className={styles.bar}>
        <Button variant="secondary" className={styles.barButton} onClick={() => select(null)}>
          新しく依頼する
        </Button>
        <Button variant="secondary" className={styles.barButton} onClick={() => void clear()} disabled={thinking}>
          最初からやり直す
        </Button>
        {events.map((e) => (
          <button
            key={e.event_id}
            type="button"
            className={`${styles.eventTab} ${e.event_id === selected ? styles.eventTabActive : ""}`}
            onClick={() => select(e.event_id)}
          >
            {e.title || "（題名未定）"}
            <Pill tone={e.status === "closed" ? "lagoon" : "navy"}>{STATUS_LABEL[e.status] ?? e.status}</Pill>
          </button>
        ))}
        <details className={styles.about}>
          <summary>この画面の見かた</summary>
          <p>{copy.banner}</p>
        </details>
      </div>

      {blocked && (
        <ErrorBanner>
          この画面は、登録した開発者のアカウントだけが使えます。体験するときは、上の「体験」を開いてください。
        </ErrorBanner>
      )}
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {notice && <InfoBanner>{notice}</InfoBanner>}

      <PhaseStepper detail={detail} />

      {/* 幹事・参加者・承認者の3人ぶんの「KUROKO との DM」。最初から、3つとも開いておく */}
      <div className={styles.columns}>
        <section className={styles.dm} aria-label="幹事と KUROKO のチャット">
          <header className={styles.dmHead}>
            <ChatAvatar who="kuroko" name="KUROKO" />
            <div className={styles.dmWho}>
              <span className={styles.dmName}>KUROKO</span>
              <Caption>幹事（あなた）との DM</Caption>
            </div>
            {done ? (
              <Pill tone="lagoon">完了</Pill>
            ) : !hint || hint.who === "幹事" ? (
              <Pill tone="sun">あなたの番です</Pill>
            ) : (
              <Pill tone="navy">{hint.who}の対応待ち</Pill>
            )}
          </header>
          {hint && <ScenarioHint hint={hint} compact />}
          <Thread label="幹事と KUROKO のやりとり" follow={follow}>
            <KurokoRow>
              はじめまして、KUROKO です。飲み会の幹事の仕事（出欠・お店選び・按分・集金）を、会社の規程に沿って
              代行します。まずは、下の入力欄から、やりたい会を教えてください。
            </KurokoRow>
            {items.map((item) =>
              item.type === "image" ? (
                <MineRow key={item.key} at={item.at} note={item.sending ? "送信中" : IMAGE_LABEL[item.kind]}>
                  <MinePhoto url={item.url} label={`${IMAGE_LABEL[item.kind]}の画像`} />
                </MineRow>
              ) : item.mine ? (
                <MineRow key={item.key} at={item.at}>
                  <MineBubble>{item.text}</MineBubble>
                </MineRow>
              ) : (
                <Fragment key={item.key}>
                  <KurokoRow at={item.at}>{item.text}</KurokoRow>
                  {detail && !viewOnly && item.card && anchorAt.get(item.card) === item.key && (
                    <AnchoredCard
                      kind={item.card}
                      detail={detail}
                      onDone={() => refresh(detail.event_id)}
                      run={run}
                    />
                  )}
                </Fragment>
              ),
            )}
            {showOutgoing && (
              <MineRow note="送信中">
                <MineBubble>{outgoing}</MineBubble>
              </MineRow>
            )}
            {thinking && (
              <KurokoWorking hint="規程の確認やお店の検索があると、30秒ほどかかることがあります">
                KUROKO が考えています…
              </KurokoWorking>
            )}
            {imageBusy && (
              <KurokoWorking hint="画像の中の文字を読み取っています">画像を読み取っています…</KurokoWorking>
            )}
            {detail && !viewOnly && (
              <StepForms
                key={detail.event_id}
                detail={detail}
                onDone={() => refresh(detail.event_id)}
                run={run}
                onSendSample={(kind) => void sendSample(kind)}
                imageBusy={imageBusy}
                computing={computing}
                onSplitStarted={() => setComputing(true)}
                onRestart={() => void clear()}
                anchored={anchored}
              />
            )}
          </Thread>
          {viewOnly ? (
            <div className={styles.composer}>
              <Caption>
                実演用: 幹事の操作（お店選び・画像の送信・確認・承認の依頼）は、Slack の DM の KUROKO で行います。
                この画面は、進み具合と、3人ぶんのやりとりを映します。
              </Caption>
            </div>
          ) : (
          <div className={styles.composer}>
            {suggestions.length > 0 && !blocked && !done && (
              <div className={styles.suggestions} role="group" aria-label="入力の候補">
                {suggestions.map((text) => (
                  <button
                    key={text}
                    type="button"
                    className={styles.suggestion}
                    onClick={() => {
                      setDraft(text);
                      inputRef.current?.focus();
                    }}
                  >
                    {text}
                  </button>
                ))}
              </div>
            )}
            <div className={styles.inputRow}>
              <button
                type="button"
                className={styles.attach}
                disabled={!imageKind || imageBusy || blocked}
                title={
                  imageKind
                    ? `${IMAGE_LABEL[imageKind]}の画像を送る`
                    : "画像は、店を選んだあと（予約の画面）と、開催のあと（領収書）に送れます"
                }
                onClick={() => fileRef.current?.click()}
              >
                <Icon name="image" label="画像を送る" />
              </button>
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPT.join(",")}
                className="visually-hidden"
                tabIndex={-1}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (file) void sendImage(file);
                }}
              />
              <label htmlFor="kuroko-message" className="visually-hidden">
                KUROKO へのメッセージ
              </label>
              <textarea
                id="kuroko-message"
                ref={inputRef}
                className={styles.textarea}
                rows={1}
                value={draft}
                placeholder={imageKind ? `メッセージ、または${IMAGE_LABEL[imageKind]}の画像を送る` : "KUROKO にメッセージを送る"}
                onChange={(e) => setDraft(e.target.value)}
                onPaste={(e) => {
                  // 画像の貼り付けは、画像の送信として扱う（DM に画像を貼るのと同じ）
                  const file = Array.from(e.clipboardData.items)
                    .find((i) => i.kind === "file" && i.type.startsWith("image/"))
                    ?.getAsFile();
                  if (file) {
                    e.preventDefault();
                    void sendImage(file);
                  }
                }}
                onKeyDown={(e) => {
                  // Enter は改行、Ctrl/⌘+Enter で送信
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    void send();
                  }
                }}
              />
              <Button className={styles.send} onClick={() => void send()} disabled={thinking || blocked || !draft.trim()}>
                <Icon name="send" size="sm" />
                送る
              </Button>
            </div>
            <Caption>Ctrl / ⌘ + Enter で送信。実在の個人情報・領収書は入れないでください。</Caption>
          </div>
          )}
        </section>
        {personas.map((p) => (
          <PersonaChat
            key={p.user_id}
            persona={p}
            role={p.user_id === approverId ? "承認者" : "参加者"}
            readOnly={live}
            onPress={
              detail && !live
                ? (card, index, inputs) =>
                    run(async () => {
                      await pressPersonaCard(detail.event_id, card.card_id, index, inputs);
                      await refresh(detail.event_id);
                    })
                : undefined
            }
            onApproveBank={
              detail && !live && detail.bank_approval === "web"
                ? () =>
                    run(async () => {
                      await approveBank(detail.event_id, p.user_id);
                      await refresh(detail.event_id);
                    }, "銀行で承認しました。1〜2分で、入金の確認に進みます。")
                : undefined
            }
            bankAmountYen={detail?.payments.find((pay) => pay.payer_user_id === p.user_id)?.amount_yen ?? null}
          />
        ))}
      </div>
    </main>
  );
}
