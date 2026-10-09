"use client";

// 検証用の画面（/verify）。実 API（/api/dashboard/*）につないで、依頼 → 計画の確定 → 店 → 予約 → 領収書までを
// 通して確かめる。チャットは検証用で、最終的には Slack に統合する（SPEC 7.5）。
// 委任・承認・振込の操作は置かない（Slack・銀行で行う。進行ヒントが案内する）。
import { useCallback, useEffect, useState } from "react";
import {
  confirmExtraction,
  confirmPlan,
  errorText,
  getEvent,
  getMe,
  listEvents,
  selectVenue,
  sendMessage,
  uploadFile,
} from "@/lib/api-client";
import type { ApiEventDetail, ApiEventSummary, ApiRole } from "@/lib/api-types";
import { useAuth } from "@/lib/auth";
import type { ChatMessage } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";
import { ScenarioHint } from "./ScenarioHint";
import { Button, Card, Caption, ErrorBanner, InfoBanner, Pill } from "./ui";
import event from "./event.module.css";
import styles from "./verify.module.css";

const POLL_MS = 5000;

function toChat(detail: ApiEventDetail): ChatMessage[] {
  return detail.messages.map((m) => ({
    messageId: m.message_id,
    role: m.role,
    text: m.text,
    createdAt: m.created_at,
  }));
}

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <label className={styles.field}>
      {label}
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function VerifyView() {
  const { user } = useAuth();
  const [role, setRole] = useState<ApiRole | null>(null);
  const [events, setEvents] = useState<ApiEventSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApiEventDetail | null>(null);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

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
      const list = await listEvents();
      setEvents(list);
      if (id) setDetail(await getEvent(id));
    },
    [],
  );

  useEffect(() => {
    if (!user) return;
    void run(async () => {
      setRole((await getMe()).role);
      await refresh(selected);
    });
  }, [user, selected, refresh, run]);

  // Slack や銀行での操作で状態が進むので、一定の間隔で読み直す
  useEffect(() => {
    if (!user || !selected) return;
    const t = setInterval(() => void refresh(selected).catch(() => undefined), POLL_MS);
    return () => clearInterval(t);
  }, [user, selected, refresh]);

  const send = async (text: string) => {
    setThinking(true);
    const ok = await run(async () => {
      const out = await sendMessage(text, selected ?? undefined);
      setSelected(out.event_id);
      await refresh(out.event_id);
    });
    if (ok) setDraft("");
    setThinking(false);
  };

  return (
    <main className={event.page}>
      <div className={event.pageHead}>
        <div>
          <h1 className={event.pageTitle}>動作の検証</h1>
          <p className={event.pageMeta}>
            実際の API につないで、依頼から領収書の確定まで通して確かめる画面です
            {role && `（${role === "guest" ? "ゲスト：体験用のイベント" : "幹事"}）`}
          </p>
        </div>
      </div>
      <InfoBanner>
        チャットは検証用です。最終的な依頼や回答は Slack で行います。委任・承認・振込は、この画面では行わず、
        Slack と銀行で行います（進行ヒントが案内します）。
      </InfoBanner>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {notice && <InfoBanner>{notice}</InfoBanner>}

      <div className={styles.layout}>
        <aside className={styles.side}>
          <Button
            variant="secondary"
            onClick={() => {
              setSelected(null);
              setDetail(null);
            }}
          >
            新しく依頼する
          </Button>
          {events.map((e) => (
            <button
              key={e.event_id}
              type="button"
              className={`${styles.eventButton} ${e.event_id === selected ? styles.eventButtonActive : ""}`}
              onClick={() => setSelected(e.event_id)}
            >
              <span className={styles.eventTitle}>{e.title || "（題名未定）"}</span>
              <Pill tone="navy">{e.status}</Pill>
            </button>
          ))}
        </aside>

        <div className={styles.main}>
          {detail && <ScenarioHint hint={detail.hint} onUseChat={setDraft} />}
          <Card title="KUROKO に依頼する" description="最初の発言で、計画中のイベントが作られます">
            <ChatPanel
              bare
              title=""
              messages={detail ? toChat(detail) : []}
              onSend={(t) => void send(t)}
              thinking={thinking}
              initialDraft={draft}
            />
          </Card>
          {detail && (
            <StepForms
              detail={detail}
              onDone={() => refresh(detail.event_id)}
              run={run}
            />
          )}
        </div>
      </div>
    </main>
  );
}

function StepForms({
  detail,
  onDone,
  run,
}: {
  detail: ApiEventDetail;
  onDone: () => Promise<void>;
  run: (fn: () => Promise<unknown>, done?: string) => Promise<boolean>;
}) {
  const id = detail.event_id;
  const ex = (detail.hint.example ?? {}) as Record<string, Record<string, unknown>>;
  const s = detail.status;
  return (
    <>
      {s === "planning" && <PlanForm id={id} example={ex.plan} onDone={onDone} run={run} />}
      {(s === "rsvp" || s === "venue") && <VenueForm id={id} onDone={onDone} run={run} />}
      {s === "booked" && (
        <ReservationForm id={id} example={ex.reservation} onDone={onDone} run={run} />
      )}
      {(s === "day_of" || s === "receipt") && (
        <ReceiptForm id={id} example={ex.receipt} detail={detail} onDone={onDone} run={run} />
      )}
      {detail.waiting_for && detail.waiting_for.where !== "web" && (
        <Caption>
          いまは {detail.waiting_for.where === "slack" ? "Slack" : "銀行"} での対応待ちです（
          {detail.waiting_for.what}）。この画面からは操作できません。
        </Caption>
      )}
    </>
  );
}

type FormProps = {
  id: string;
  onDone: () => Promise<void>;
  run: (fn: () => Promise<unknown>, done?: string) => Promise<boolean>;
};

function PlanForm({ id, example, onDone, run }: FormProps & { example?: Record<string, unknown> }) {
  const [v, setV] = useState({
    title: String(example?.title ?? ""),
    datetime: "",
    area: String(example?.area ?? ""),
    party: String(example?.party_size ?? ""),
    budget: String(example?.budget_per_person_yen ?? ""),
  });
  const set = (k: keyof typeof v) => (x: string) => setV((p) => ({ ...p, [k]: x }));
  return (
    <Card title="計画を確定する" description="確定すると、参加者に Slack で出欠依頼が届きます">
      <div className={styles.form}>
        <Field label="題名" value={v.title} onChange={set("title")} />
        <Field label="日時" type="datetime-local" value={v.datetime} onChange={set("datetime")} />
        <Field label="エリア" value={v.area} onChange={set("area")} />
        <Field label="人数（2〜50）" type="number" value={v.party} onChange={set("party")} />
        <Field label="1人あたりの予算（円）" type="number" value={v.budget} onChange={set("budget")} />
        <div className={styles.formActions}>
          <Button
            onClick={() =>
              void run(async () => {
                await confirmPlan(id, {
                  title: v.title,
                  datetime: v.datetime ? new Date(v.datetime).toISOString() : "",
                  area: v.area,
                  party_size: Number(v.party),
                  budget_per_person_yen: Number(v.budget),
                  required_tags: [],
                });
                await onDone();
              }, "計画を確定しました。参加者に出欠依頼を送っています。")
            }
          >
            この内容で進める
          </Button>
        </div>
      </div>
    </Card>
  );
}

function VenueForm({ id, onDone, run }: FormProps) {
  const [name, setName] = useState("");
  const [placeId, setPlaceId] = useState("");
  return (
    <Card title="店を選ぶ" description="チャットで「お店を探して」と頼み、出た候補から店の名前を入れます">
      <div className={styles.form}>
        <Field label="店の名前" value={name} onChange={setName} />
        <Field label="Google の place ID（任意）" value={placeId} onChange={setPlaceId} />
        <div className={styles.formActions}>
          <Button
            onClick={() =>
              void run(async () => {
                await selectVenue(id, placeId || `manual-${name}`, name);
                await onDone();
              }, "店を選びました。")
            }
          >
            この店にする
          </Button>
        </div>
      </div>
    </Card>
  );
}

function ReservationForm({ id, example, onDone, run }: FormProps & { example?: Record<string, unknown> }) {
  const [v, setV] = useState({
    venue: String(example?.venue_name ?? ""),
    datetime: "",
    party: String(example?.party_size ?? ""),
    price: String(example?.course_price_yen ?? ""),
  });
  const set = (k: keyof typeof v) => (x: string) => setV((p) => ({ ...p, [k]: x }));
  return (
    <Card title="予約の内容を確定する" description="手入力でも、読み取りと同じ検査を通ります">
      <div className={styles.form}>
        <Field label="店名" value={v.venue} onChange={set("venue")} />
        <Field label="日時" type="datetime-local" value={v.datetime} onChange={set("datetime")} />
        <Field label="人数" type="number" value={v.party} onChange={set("party")} />
        <Field label="コース単価（円）" type="number" value={v.price} onChange={set("price")} />
        <div className={styles.formActions}>
          <Button
            onClick={() =>
              void run(async () => {
                await confirmExtraction(
                  id,
                  "reservation",
                  {
                    venue_name: v.venue,
                    datetime: v.datetime ? new Date(v.datetime).toISOString() : "",
                    party_size: Number(v.party),
                    course_price_yen: Number(v.price),
                  },
                  "manual",
                );
                await onDone();
              }, "予約の内容を確定しました。")
            }
          >
            この内容で確定する
          </Button>
        </div>
      </div>
    </Card>
  );
}

function ReceiptForm({
  id,
  example,
  detail,
  onDone,
  run,
}: FormProps & { example?: Record<string, unknown>; detail: ApiEventDetail }) {
  const [amount, setAmount] = useState(String(example?.total_amount_yen ?? ""));
  const failed = detail.uploads.some((u) => u.kind === "receipt" && u.extraction_status === "failed");
  return (
    <Card
      title="領収書の金額を確定する"
      description="ファイルをアップロードして読み取り結果を確認します。手入力は、読み取りに失敗したときだけです"
    >
      <div className={styles.uploadRow}>
        <input
          type="file"
          accept="image/jpeg,image/png,application/pdf"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f)
              void run(async () => {
                await uploadFile(id, "receipt", f);
                await onDone();
              }, "アップロードしました。読み取りを待っています。");
          }}
        />
      </div>
      <ul className={styles.uploadList}>
        {detail.uploads.map((u) => (
          <li key={u.upload_id}>
            {u.kind === "receipt" ? "領収書" : "予約画面"}：{u.status}（読み取り：{u.extraction_status}）
          </li>
        ))}
      </ul>
      <div className={styles.form}>
        <Field label="合計金額（円）" type="number" value={amount} onChange={setAmount} />
        <div className={styles.formActions}>
          <Button
            disabled={!failed}
            onClick={() =>
              void run(async () => {
                await confirmExtraction(id, "receipt", { total_amount_yen: Number(amount) }, "manual");
                await onDone();
              }, "金額を確定しました。按分に進みます。")
            }
          >
            手入力で確定する
          </Button>
        </div>
      </div>
      {!failed && <Caption>読み取りの結果の確認は、読み取りの機能（B19）ができてから使えます。</Caption>}
    </Card>
  );
}

