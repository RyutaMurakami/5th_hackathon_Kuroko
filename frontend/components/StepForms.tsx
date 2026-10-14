"use client";

// 段階ごとの入力（計画・店・予約・領収書・振り返り）。チャットの流れの中に、**KUROKO からの発言（カード）**
// として出す（必要な入力は、チャットの中で完結する。SPEC 7.5）。入力欄には、デモ用の候補を入れておく。
// 予約の画面・領収書は、チャットに画像を送って渡す（アップロードの欄は置かない）。
// 委任・承認・振込の操作は置かない（参加者・承認者の列、Slack、銀行で行う）。
import { useEffect, useState } from "react";
import {
  closeRetro,
  confirmBudgetOverrun,
  confirmExtraction,
  confirmPlan,
  confirmRetro,
  findVenues,
  markHeld,
  requestApproval,
  approveTransfers,
  selectVenue,
} from "@/lib/api-client";
import type { ApiEventDetail, ApiPlanExample, ApiRetro, ApiSplit, ApiVenueCandidate } from "@/lib/api-types";
import { formatDateTime } from "@/lib/format";
import { KurokoRow, KurokoWorking, chatStyles as styles } from "./ChatThread";
import { Icon } from "./Icon";
import { Button, ButtonLink, Caption, Pill, Progress } from "./ui";

export type ImageKind = "reservation" | "receipt";

type Run = (fn: () => Promise<unknown>, done?: string) => Promise<boolean>;

type FormProps = {
  id: string;
  onDone: () => Promise<void>;
  run: Run;
};

/** いまの段階で、チャットに送った画像を何として受け取るか（受け取らない段階では null） */
export function expectedImage(detail: ApiEventDetail | null): ImageKind | null {
  if (!detail) return null;
  if (detail.status === "venue" && chosenPlaceId(detail)) return "reservation";
  if (detail.status === "day_of" || detail.status === "receipt") return "receipt";
  return null;
}

function chosenPlaceId(detail: ApiEventDetail): string | null {
  return typeof detail.venue?.place_id === "string" ? detail.venue.place_id : null;
}

/** Google マップで、その店を開く URL（公開の検索 URL） */
function mapsUrl(name: string, placeId: string): string {
  const url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name)}`;
  return placeId && !placeId.startsWith("manual-") ? `${url}&query_place_id=${encodeURIComponent(placeId)}` : url;
}

/** 押してから終わるまで、ボタンを「送信中」にする（二重に押させない） */
function useBusy(): [boolean, (fn: () => Promise<unknown>) => Promise<void>] {
  const [busy, setBusy] = useState(false);
  const act = async (fn: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  };
  return [busy, act];
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  wide = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  wide?: boolean;
  placeholder?: string;
}) {
  return (
    <label className={`${styles.field} ${wide ? styles.wide : ""}`}>
      {label}
      <input type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

/** 状態つきのカード（発言の位置に出す。時系列を崩さない）の種類 */
export type AnchorKind = "plan" | "venues" | "split" | "transfer" | "retro";

/** 状態が揃っていて、発言の位置に出せるカードの種類 */
export function anchorsAvailable(detail: ApiEventDetail): AnchorKind[] {
  const out: AnchorKind[] = [];
  if (detail.status === "planning") out.push("plan");
  if (detail.venue_candidates.length > 0) out.push("venues");
  if (detail.split) out.push("split");
  if (detail.split && ["approval", "payment", "completed", "retro", "closed"].includes(detail.status)) {
    // 承認者が承認したあと（「承認しました」の発言に付く）
    if (detail.split.approval.status === "approved") out.push("transfer");
  }
  if (detail.retro) out.push("retro");
  return out;
}

/** 発言の位置に出すカード */
export function AnchoredCard({
  kind,
  detail,
  onDone,
  run,
}: {
  kind: AnchorKind;
  detail: ApiEventDetail;
  onDone: () => Promise<void>;
  run: Run;
}) {
  const base = { id: detail.event_id, onDone, run };
  if (kind === "plan") {
    const ex = (detail.hint.example ?? {}) as Record<string, Record<string, unknown>>;
    return <PlanForm {...base} example={ex.plan as ApiPlanExample | undefined} />;
  }
  if (kind === "venues") return <VenueStep {...base} detail={detail} />;
  if (kind === "split" && detail.split) return <SplitCard {...base} split={detail.split} detail={detail} />;
  if (kind === "transfer") return <TransferCard {...base} detail={detail} />;
  if (kind === "retro" && detail.retro) return <RetroCard {...base} retro={detail.retro} />;
  return null;
}

/**
 * チャットの流れの最後に出す、**いま入力が要る**カード。状態つきのカード（店の候補・按分の内訳・
 * 振込の依頼・振り返り）は、それぞれの発言の位置に出す（`AnchoredCard`）ので、`anchored` に
 * 入っている種類は、ここでは出さない。
 */
export function StepForms({
  detail,
  onDone,
  run,
  onSendSample,
  imageBusy,
  computing,
  onSplitStarted,
  onRestart,
  anchored,
}: {
  detail: ApiEventDetail;
  onDone: () => Promise<void>;
  run: Run;
  /** サンプルの画像（予約の画面・領収書）を、チャットに送る */
  onSendSample: (kind: ImageKind) => void;
  /** 画像を送って、読み取りを待っているあいだ */
  imageBusy: boolean;
  /** 領収書の金額を確定して、按分の結果を待っているあいだ */
  computing: boolean;
  /** 領収書の金額を確定した（按分の計算が始まる） */
  onSplitStarted: () => void;
  /** デモの終わりの「最初からやり直す」 */
  onRestart: () => void;
  /** 発言の位置に出している種類 */
  anchored: ReadonlySet<AnchorKind>;
}) {
  const id = detail.event_id;
  const ex = (detail.hint.example ?? {}) as Record<string, Record<string, unknown>>;
  const s = detail.status;
  const chosen = chosenPlaceId(detail);
  const base = { id, onDone, run };
  const waitingSplit = (computing || s === "split") && !detail.split;
  const lonely = (kind: AnchorKind) => anchorsAvailable(detail).includes(kind) && !anchored.has(kind);
  return (
    <>
      {s === "venue" && detail.venue_candidates.length === 0 && <VenueStep {...base} detail={detail} />}
      {lonely("venues") && <VenueStep {...base} detail={detail} />}
      {s === "venue" && chosen && (
        <ReservationStep
          {...base}
          example={ex.reservation}
          detail={detail}
          onSendSample={() => onSendSample("reservation")}
          imageBusy={imageBusy}
        />
      )}
      {s === "venue" && detail.budget_overrun && <BudgetOverrunCard {...base} over={detail.budget_overrun} />}
      {s === "booked" && <HeldCard {...base} />}
      {(s === "day_of" || s === "receipt") && (
        <ReceiptStep
          {...base}
          example={ex.receipt}
          detail={detail}
          onSendSample={() => onSendSample("receipt")}
          imageBusy={imageBusy}
          onSplitStarted={onSplitStarted}
        />
      )}
      {waitingSplit && <ComputingSplit />}
      {lonely("split") && detail.split && <SplitCard {...base} split={detail.split} detail={detail} />}
      {lonely("transfer") && <TransferCard {...base} detail={detail} />}
      {s === "completed" && !detail.retro && (
        <KurokoWorking>全員の入金を確認しました。参加者に、振り返りのお願いを送っています…</KurokoWorking>
      )}
      {lonely("retro") && detail.retro && <RetroCard {...base} retro={detail.retro} />}
      {s === "closed" && <Finale detail={detail} onRestart={onRestart} />}
    </>
  );
}

// ------------------------------------------------------------------ 計画
function PlanForm({ id, example, onDone, run }: FormProps & { example?: ApiPlanExample }) {
  const [v, setV] = useState({
    title: String(example?.title ?? ""),
    datetime: String(example?.datetime ?? ""),
    party: String(example?.party_size ?? ""),
    budget: String(example?.budget_per_person_yen ?? ""),
    deadline: String(example?.rsvp_deadline ?? ""),
  });
  const options = example?.honorees ?? [];
  const [honorees, setHonorees] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(options.map((h) => [h.user_id, h.selected])),
  );
  const [busy, act] = useBusy();
  const set = (k: keyof typeof v) => (x: string) => setV((p) => ({ ...p, [k]: x }));
  const submit = () =>
    act(() =>
      run(async () => {
        await confirmPlan(id, {
          title: v.title,
          datetime: v.datetime ? new Date(v.datetime).toISOString() : "",
          party_size: Number(v.party),
          budget_per_person_yen: Number(v.budget),
          required_tags: [],
          rsvp_deadline: v.deadline || undefined,
          // 名簿の主役は、サーバーが主役のままにする。送るのは、足したぶんだけ
          guests_of_honor: options.filter((h) => !h.locked && honorees[h.user_id]).map((h) => h.user_id),
        });
        await onDone();
      }),
    );
  return (
    <KurokoRow card>
      <span className={styles.cardTitle}>次の内容で進めてよいですか？</span>
      <span>
        直すところがあれば直して、「この内容で進める」を押してください。お店の場所は、参加者の最寄り駅から
        探すので、ここでは決めません。
      </span>
      <div className={styles.form}>
        <Field label="題名" value={v.title} onChange={set("title")} wide />
        <Field label="日時" type="datetime-local" value={v.datetime} onChange={set("datetime")} />
        <Field label="出欠の回答期限" type="date" value={v.deadline} onChange={set("deadline")} />
        <Field label="人数（2〜50）" type="number" value={v.party} onChange={set("party")} />
        <Field label="1人あたりの予算（円）" type="number" value={v.budget} onChange={set("budget")} />
        {options.length > 0 && (
          <fieldset className={`${styles.group} ${styles.wide}`}>
            <legend>主役（歓迎・送別される方。費用の案内は届きません）</legend>
            <div className={styles.choices}>
              {options.map((h) => (
                <label key={h.user_id} className={styles.choice}>
                  <input
                    type="checkbox"
                    checked={honorees[h.user_id] ?? false}
                    disabled={h.locked}
                    onChange={(e) => setHonorees((p) => ({ ...p, [h.user_id]: e.target.checked }))}
                  />
                  {h.display_name}
                </label>
              ))}
            </div>
          </fieldset>
        )}
      </div>
      <div className={styles.actions}>
        <Button onClick={() => void submit()} disabled={busy}>
          {busy ? "送信中…（参加者に依頼を送っています）" : "この内容で進める"}
        </Button>
      </div>
      <Caption>確定すると、参加者に、出欠・支払いの委任・最寄り駅・苦手な食べ物の確認が届きます。</Caption>
    </KurokoRow>
  );
}

// ------------------------------------------------------------------ 店
const SEARCH_RETRY_AFTER_MS = 60_000;

function VenueStep({ id, detail, onDone, run }: FormProps & { detail: ApiEventDetail }) {
  const [busy, act] = useBusy();
  const [picking, setPicking] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const [name, setName] = useState("");
  const [showAll, setShowAll] = useState(false);
  const candidates = detail.venue_candidates;
  const chosen = chosenPlaceId(detail);
  const search = detail.venue_search?.status ?? "";
  // 自動の検索が長引いたとき（タスクが動かなかったとき）は、幹事が探し直せる
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (search !== "searching") return;
    const t = setTimeout(() => setSlow(true), SEARCH_RETRY_AFTER_MS);
    return () => clearTimeout(t);
  }, [search]);
  const retry = () =>
    act(() =>
      run(async () => {
        await findVenues(id);
        await onDone();
      }),
    );
  const pick = async (placeId: string, venueName: string) => {
    setPicking(placeId);
    await run(async () => {
      await selectVenue(id, placeId, venueName);
      await onDone();
    });
    setPicking(null);
  };

  if (candidates.length === 0 && (busy || (search === "searching" && !slow))) {
    return (
      <KurokoWorking hint="駅すぱあとで全員の帰りやすい駅を調べ、Google マップでお店を探すので、30秒ほどかかります">
        全員の最寄り駅から、帰りやすいお店を探しています…
      </KurokoWorking>
    );
  }
  if (candidates.length === 0) {
    return (
      <KurokoRow card>
        <span className={styles.cardTitle}>
          {search === "failed" ? "お店を見つけられませんでした" : "お店を探します"}
        </span>
        <span>
          全員の最寄り駅からの帰りやすさ・苦手な食べ物・過去の実績（記憶）から、候補を出します。順位は、
          決まった手順のコードが決めます。
        </span>
        <div className={styles.actions}>
          <Button onClick={() => void retry()}>{search === "" ? "店の候補を出す" : "もう一度探す"}</Button>
          <button type="button" className={styles.link} onClick={() => setManual(true)}>
            候補に無い店を、名前で入れる
          </button>
        </div>
        {manual && <ManualVenue name={name} setName={setName} onPick={() => void pick(`manual-${name}`, name)} />}
      </KurokoRow>
    );
  }
  const picked = candidates.some((c) => c.place_id === chosen);
  // 予約の確定のあと（店の選択の段階を過ぎたあと）は、選び直せない
  const locked = detail.status !== "venue";
  return (
    <KurokoRow card>
      <div className={styles.cardHead}>
        <span className={styles.cardTitle}>お店の候補</span>
        {chosen && <Pill tone="lagoon">選択済み</Pill>}
      </div>
      <div className={styles.rows}>
        {candidates.map((c, i) =>
          // 選んだあとは、選んだ店だけを出す（ほかの候補は、たたむ）
          picked && !showAll && c.place_id !== chosen ? null : (
            <VenueItem
              key={c.place_id}
              rank={i + 1}
              venue={c}
              chosen={c.place_id === chosen}
              busy={picking === c.place_id}
              disabled={picking !== null || locked}
              onPick={() => void pick(c.place_id, c.name)}
            />
          ),
        )}
      </div>
      <Caption>
        アレルゲンは、お店に確認してください。予約は、幹事がお店で行います（KUROKO は予約しません）。
      </Caption>
      {locked ? null : picked && !showAll ? (
        <button type="button" className={styles.link} onClick={() => setShowAll(true)}>
          ほかの候補を見る・選び直す
        </button>
      ) : manual ? (
        <ManualVenue name={name} setName={setName} onPick={() => void pick(`manual-${name}`, name)} />
      ) : (
        <button type="button" className={styles.link} onClick={() => setManual(true)}>
          候補に無い店を、名前で入れる
        </button>
      )}
    </KurokoRow>
  );
}

function VenueItem({
  rank,
  venue: c,
  chosen,
  busy,
  disabled,
  onPick,
}: {
  rank: number;
  venue: ApiVenueCandidate;
  chosen: boolean;
  busy: boolean;
  disabled: boolean;
  onPick: () => void;
}) {
  const yen = (n: number | null) => (n === null ? "—" : n.toLocaleString());
  return (
    <div className={`${styles.venue} ${chosen ? styles.venueChosen : ""}`}>
      <span className={styles.venueName}>
        {rank}. {c.name}
      </span>
      <span className={styles.meta}>
        {c.nearest_station}駅・最も遠い方で {c.max_travel_minutes}分（平均 {c.avg_travel_minutes}分）・1人{" "}
        {yen(c.price_min_yen)}〜{yen(c.price_max_yen)}円
      </span>
      <span>{c.selection_reason}</span>
      {c.memory_note && (
        <span className={styles.memory}>
          <Pill tone="sun">記憶</Pill> {c.memory_note}
        </span>
      )}
      <div className={styles.actions}>
        {chosen ? (
          // 選んだ店は、ボタンから Google マップで確かめられる（別のタブで開く）
          <ButtonLink href={mapsUrl(c.name, c.place_id)} external>
            <Icon name="map" size="sm" />
            選択中（Google マップで見る）
          </ButtonLink>
        ) : (
          <>
            <Button onClick={onPick} disabled={disabled}>
              {busy ? "送信中…" : "この店にする"}
            </Button>
            <ButtonLink variant="secondary" href={mapsUrl(c.name, c.place_id)} external>
              <Icon name="map" size="sm" />
              Google マップで見る
            </ButtonLink>
          </>
        )}
      </div>
    </div>
  );
}

function ManualVenue({ name, setName, onPick }: { name: string; setName: (v: string) => void; onPick: () => void }) {
  return (
    <div className={styles.form}>
      <Field label="店の名前（候補に無い店）" value={name} onChange={setName} wide />
      <div className={`${styles.actions} ${styles.wide}`}>
        <Button variant="secondary" onClick={onPick} disabled={!name.trim()}>
          この店にする
        </Button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 予約
/** ISO の日時を、`datetime-local` の入力欄の形（その端末の時刻）にする */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

/**
 * 予約の内容。**店を選んだだけでは、入力欄を出さない**（幹事が、まずお店に予約する）。
 * 予約完了の画面をチャットに送る（または「手入力する」を選ぶ）と、確かめるカードを出す。
 */
function ReservationStep({
  id,
  example,
  detail,
  onDone,
  run,
  onSendSample,
  imageBusy,
}: FormProps & {
  example?: Record<string, unknown>;
  detail: ApiEventDetail;
  onSendSample: () => void;
  imageBusy: boolean;
}) {
  const chosenName = typeof detail.venue?.name === "string" ? detail.venue.name : "";
  const [v, setV] = useState({
    venue: chosenName || String(example?.venue_name ?? ""),
    datetime: toLocalInput(detail.datetime),
    party: String(example?.party_size ?? ""),
    price: String(example?.course_price_yen ?? ""),
  });
  const set = (k: keyof typeof v) => (x: string) => setV((p) => ({ ...p, [k]: x }));
  const [manual, setManual] = useState(false);
  const [busy, act] = useBusy();
  const uploads = detail.uploads.filter((u) => u.kind === "reservation" && u.status === "registered");
  const read = [...uploads].reverse().find((u) => u.extraction) ?? null;
  const reading = read?.extraction ?? null;
  const failed = !reading && uploads.some((u) => u.extraction_status === "failed");
  const [seeded, setSeeded] = useState<string | null>(null);
  // 読み取れた値を入力欄に入れる（幹事が見て直せる。確定するまで使われない）
  if (read && reading && seeded !== read.upload_id) {
    setSeeded(read.upload_id);
    setV((p) => ({
      venue: reading.venue_name ?? p.venue,
      datetime: reading.datetime ? toLocalInput(reading.datetime) : p.datetime,
      party: reading.party_size != null ? String(reading.party_size) : p.party,
      price: reading.course_price_yen != null ? String(reading.course_price_yen) : p.price,
    }));
  }
  if (detail.budget_overrun) return null; // 確定済み（予算超過の確認待ち）
  const confirm = (source: "extracted" | "manual") =>
    act(() =>
      run(async () => {
        await confirmExtraction(
          id,
          "reservation",
          {
            venue_name: v.venue,
            datetime: v.datetime ? new Date(v.datetime).toISOString() : "",
            party_size: Number(v.party),
            course_price_yen: Number(v.price),
          },
          source,
        );
        await onDone();
      }),
    );

  if (!reading && !failed && !manual) {
    if (imageBusy) return null; // 読み取り中（「読み取っています」を、呼び出し側が出す）
    return (
      <KurokoRow card>
        <span>
          お店に予約したら、<strong>予約完了の画面（スクリーンショット）を、このチャットに送ってください</strong>
          。下の入力欄の画像ボタン（または貼り付け）から送れます。内容を読み取って、確認のカードをお出しします。
        </span>
        <div className={styles.actions}>
          <Button variant="secondary" onClick={onSendSample}>
            <Icon name="image" size="sm" />
            サンプルの予約画面を送る
          </Button>
          <button type="button" className={styles.link} onClick={() => setManual(true)}>
            画像なしで、手入力する
          </button>
        </div>
        <Caption>体験用です。実在の予約画面・個人情報は送らないでください。</Caption>
      </KurokoRow>
    );
  }
  return (
    <KurokoRow card>
      <span className={styles.cardTitle}>予約の内容を確かめてください</span>
      <span>
        {reading
          ? "送っていただいた画面から、次のように読み取りました。違うところがあれば直して、確定してください。"
          : failed
            ? "すみません、画面を読み取れませんでした。下の欄に入力して、確定してください。"
            : "予約の内容を入力して、確定してください。"}
        {reading && reading.warnings.length > 0 && ` 注意：${reading.warnings.join("、")}`}
      </span>
      <div className={styles.form}>
        <Field label="店名" value={v.venue} onChange={set("venue")} wide />
        <Field label="日時" type="datetime-local" value={v.datetime} onChange={set("datetime")} wide />
        <Field label="人数" type="number" value={v.party} onChange={set("party")} />
        <Field label="コース単価（円）" type="number" value={v.price} onChange={set("price")} />
      </div>
      <div className={styles.actions}>
        <Button onClick={() => void confirm(reading ? "extracted" : "manual")} disabled={busy}>
          {busy ? "送信中…（参加者に案内を送っています）" : "この内容で確定する"}
        </Button>
      </div>
      <Caption>確定すると、参加者の DM に、開催の案内（日時・お店・地図）が届きます。</Caption>
    </KurokoRow>
  );
}

function BudgetOverrunCard({
  id,
  over,
  onDone,
  run,
}: FormProps & { over: NonNullable<ApiEventDetail["budget_overrun"]> }) {
  const [busy, act] = useBusy();
  return (
    <KurokoRow card>
      <span className={styles.cardTitle}>予算を超えています</span>
      <span>
        コース単価 {over.course_price_yen.toLocaleString()}円が、規程の上限 {over.limit_yen.toLocaleString()}
        円を超えています。続行するときは、幹事が確認したあと、承認者に最終確認をお願いします。
      </span>
      {over.organizer_confirmed ? (
        <Caption>幹事の確認は済みました。承認者の最終確認を待っています。</Caption>
      ) : (
        <div className={styles.actions}>
          <Button
            disabled={busy}
            onClick={() =>
              void act(() =>
                run(async () => {
                  await confirmBudgetOverrun(id);
                  await onDone();
                }),
              )
            }
          >
            {busy ? "送信中…" : "超過を確認して続行する"}
          </Button>
        </div>
      )}
    </KurokoRow>
  );
}

function HeldCard({ id, onDone, run }: FormProps) {
  const [busy, act] = useBusy();
  return (
    <KurokoRow card>
      <span>
        当日まで、お待ちください。<strong>開催が終わったら</strong>、下のボタンでお知らせください。領収書の確認に
        進みます（体験用では、開催日を待たずに押せます）。
      </span>
      <div className={styles.actions}>
        <Button
          disabled={busy}
          onClick={() =>
            void act(() =>
              run(async () => {
                await markHeld(id);
                await onDone();
              }),
            )
          }
        >
          {busy ? "送信中…" : "開催が終わった"}
        </Button>
      </div>
    </KurokoRow>
  );
}

// ------------------------------------------------------------------ 領収書
function ReceiptStep({
  id,
  example,
  detail,
  onDone,
  run,
  onSendSample,
  imageBusy,
  onSplitStarted,
}: FormProps & {
  example?: Record<string, unknown>;
  detail: ApiEventDetail;
  onSendSample: () => void;
  imageBusy: boolean;
  onSplitStarted: () => void;
}) {
  const [amount, setAmount] = useState(String(example?.total_amount_yen ?? ""));
  const [busy, act] = useBusy();
  const uploads = detail.uploads.filter((u) => u.kind === "receipt" && u.status === "registered");
  const failed = uploads.some((u) => u.extraction_status === "failed");
  const read = [...uploads].reverse().find((u) => u.extraction) ?? null;
  const reading = read?.extraction ?? null;
  const [seeded, setSeeded] = useState<string | null>(null);
  // 読み取れた金額を入力欄に入れる（幹事が見て直せる）
  if (read && reading?.total_amount_yen && seeded !== read.upload_id) {
    setSeeded(read.upload_id);
    setAmount(String(reading.total_amount_yen));
  }
  const confirm = (source: "extracted" | "manual") =>
    act(async () => {
      const ok = await run(async () => {
        await confirmExtraction(id, "receipt", { total_amount_yen: Number(amount) }, source);
      });
      if (ok) onSplitStarted();
      await onDone();
    });

  if (!reading && !failed) {
    if (imageBusy) return null; // 読み取り中
    return (
      <KurokoRow card>
        <span>
          <strong>領収書の写真を、このチャットに送ってください。</strong>
          下の入力欄の画像ボタン（または貼り付け）から送れます。金額を読み取って、確認のカードをお出しします。
        </span>
        <div className={styles.actions}>
          <Button variant="secondary" onClick={onSendSample}>
            <Icon name="image" size="sm" />
            サンプルの領収書を送る
          </Button>
        </div>
        <Caption>体験用です。実在の領収書・個人情報は送らないでください。</Caption>
      </KurokoRow>
    );
  }
  return (
    <KurokoRow card>
      <span className={styles.cardTitle}>領収書の金額を確かめてください</span>
      {reading ? (
        <>
          <span>
            領収書から、金額を読み取りました。合っていれば、確定してください。
            {reading.warnings.length > 0 && ` 注意：${reading.warnings.join("、")}`}
          </span>
          <dl className={styles.facts}>
            <dt>合計金額</dt>
            <dd>{reading.total_amount_yen?.toLocaleString()}円</dd>
            {(reading.line_items?.length ?? 0) > 0 && (
              <>
                <dt>明細</dt>
                <dd>{reading.line_items?.length}件</dd>
              </>
            )}
          </dl>
        </>
      ) : (
        <span>すみません、領収書を読み取れませんでした。合計金額を入力して、確定してください。</span>
      )}
      <div className={styles.form}>
        <Field label="合計金額（円）" type="number" value={amount} onChange={setAmount} />
      </div>
      <div className={styles.actions}>
        <Button onClick={() => void confirm(reading ? "extracted" : "manual")} disabled={busy}>
          {busy ? "送信中…" : reading ? "この金額で確定する" : "手入力で確定する"}
        </Button>
      </div>
      <Caption>確定すると、会社の規程にもとづいて、決まった手順のコードが按分を計算します（AI は金額を計算しません）。</Caption>
    </KurokoRow>
  );
}

// ------------------------------------------------------------------ 按分
const SPLIT_STEPS = [
  "会社の規程（懇親会費用規程）を確認",
  "按分ルール（負担の係数・会社の補助・端数の扱い）を適用",
  "按分を計算（決まった手順のコード。AI は金額を計算しません）",
  "規程にもとづいて承認者を決め、承認を依頼",
];
const SPLIT_STEP_MS = 1500;

/** 按分の計算の途中経過。何を見て計算しているかを、順に見せる（計算そのものは、サーバーのコード） */
function ComputingSplit() {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setNow((n) => Math.min(n + 1, SPLIT_STEPS.length - 1)), SPLIT_STEP_MS);
    return () => clearInterval(t);
  }, []);
  return (
    <KurokoRow card>
      <span className={styles.cardTitle} role="status">
        規程と按分ルールを確認して、按分を計算しています…
      </span>
      <div className={styles.steps}>
        {SPLIT_STEPS.map((text, i) => (
          <span
            key={text}
            className={`${styles.step} ${i < now ? styles.stepDone : i === now ? styles.stepNow : ""}`}
          >
            <span className={styles.stepMark} aria-hidden>
              {i < now ? "✓" : i === now ? "…" : "・"}
            </span>
            {text}
          </span>
        ))}
      </div>
    </KurokoRow>
  );
}

// 規程の値のまとまり（kuroko-api の `citations` の鍵）の呼び方
const CITATION_LABEL: Record<string, string> = {
  member_classes: "負担係数",
  subsidy: "会社の補助",
  rounding: "端数の扱い",
  approver: "承認者の決め方",
};

const PAYMENT_LABEL: Record<string, string> = {
  awaiting_bank_approval: "銀行の承認待ち",
  completed: "支払い済み",
  failed: "未完了",
  blocked: "未完了",
};

/** 按分の内訳（保存された値をそのまま出す。画面で再計算しない）と、根拠の規程（SPEC 7.3.1・9.7） */
function SplitCard({
  id,
  split,
  detail,
  onDone,
  run,
}: FormProps & { split: ApiSplit; detail: ApiEventDetail }) {
  const [busy, act] = useBusy();
  const name = (uid: string) => detail.participants.find((p) => p.user_id === uid)?.display_name ?? uid;
  // 内訳を確かめたあとに、幹事が承認者に承認を依頼する（SPEC 7.5）
  const canRequest = detail.status === "split" && split.approval.status === "pending";
  const requested = detail.status === "approval" && split.approval.status === "pending";
  const paid = (id: string) => PAYMENT_LABEL[detail.payments.find((p) => p.payer_user_id === id)?.status ?? ""];
  const cited = Object.entries(CITATION_LABEL)
    .filter(([k]) => split.policy?.citations[k])
    .map(([k, label]) => `${label}は${split.policy?.citations[k]}`);
  const approved = split.approval.status === "approved";
  return (
    <KurokoRow card>
      <div className={styles.cardHead}>
        <span className={styles.cardTitle}>按分の内訳</span>
        <Pill tone={approved ? "lagoon" : canRequest ? "navy" : "sun"}>
          {approved
            ? "承認済み"
            : canRequest
              ? "あなたの確認待ち"
              : `承認待ち（${name(split.approval.approver_user_id)}）`}
        </Pill>
      </div>
      <span>
        会計 {split.total_amount_yen.toLocaleString()}円 − 会社補助 {split.subsidy_yen.toLocaleString()}円 = 按分の対象額{" "}
        <strong>{split.base_amount_yen.toLocaleString()}円</strong>
      </span>
      <div className={styles.rows}>
        {split.rows.map((r) => (
          <div key={r.user_id} className={styles.splitRow}>
            <span>{name(r.user_id)}</span>
            <span className={styles.meta}>
              {r.weight === 0 ? "主役（負担なし）" : `係数 ${r.weight}・${r.ratio_percent.toFixed(2)}%`}
              {paid(r.user_id) ? `・${paid(r.user_id)}` : ""}
            </span>
            <span className={styles.yen}>{r.share_yen.toLocaleString()}円</span>
          </div>
        ))}
      </div>
      {canRequest && (
        <div className={styles.actions}>
          <Button
            disabled={busy}
            onClick={() =>
              void act(() =>
                run(async () => {
                  await requestApproval(id);
                  await onDone();
                }),
              )
            }
          >
            {busy ? "送信中…" : `${name(split.approval.approver_user_id)} さんに承認を依頼する`}
          </Button>
        </div>
      )}
      {requested && <Caption>承認を依頼しました。承認されるまで、お待ちください。</Caption>}
      <Caption>
        計算は、決まった手順のコードが行いました（AI は金額を計算しません）。
        {split.policy?.source === "document"
          ? ` 値は、規程の文書（懇親会費用規程）から AI が読み取り、コードが検証したものです。${cited.join("、")}。`
          : " 規程の値は、既定の値を使っています。"}
      </Caption>
    </KurokoRow>
  );
}

// ------------------------------------------------------------------ 振り返り
/** 承認者が按分を承認したあと、幹事が「参加者に振込の依頼を送る」ことを承認する（SPEC 7.5） */
function TransferCard({ id, detail, onDone, run }: FormProps & { detail: ApiEventDetail }) {
  const [busy, act] = useBusy();
  const waiting = detail.status === "approval" && detail.split?.approval.status === "approved";
  const [sent, setSent] = useState(false);
  return (
    <KurokoRow card>
      <div className={styles.cardHead}>
        <span className={styles.cardTitle}>振込の依頼を送る</span>
        <Pill tone={waiting && !sent ? "sun" : "lagoon"}>
          {waiting && !sent ? "あなたの確認待ち" : "送信済み"}
        </Pill>
      </div>
      {waiting && !sent ? (
        <>
          <span>
            承認者が按分を承認しました。参加者に、銀行で承認するお願いを送ってよければ、下のボタンを
            押してください。お金が動くのは、各自が銀行で承認したときだけです。
          </span>
          <div className={styles.actions}>
            <Button
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  const ok = await run(async () => {
                    await approveTransfers(id);
                    await onDone();
                  });
                  if (ok) setSent(true);
                })
              }
            >
              {busy ? "送信中…" : "振込の依頼を送る"}
            </Button>
          </div>
        </>
      ) : (
        <span>参加者に、銀行で承認するお願いを送りました。各自が銀行で承認すると、振込が実行されます。</span>
      )}
    </KurokoRow>
  );
}

const RETRO_PILL: Record<ApiRetro["status"], { label: string; tone: "navy" | "sun" | "lagoon" }> = {
  collecting: { label: "回答を集めています", tone: "navy" },
  awaiting_organizer: { label: "あなたの確認待ち", tone: "sun" },
  saved: { label: "記憶に保存済み", tone: "lagoon" },
  skipped: { label: "保存しない", tone: "navy" },
  expired: { label: "期限切れ", tone: "navy" },
};

const FACT_LABEL = { venue_record: "実績", venue_evaluation: "評価" } as const;

// 回答から読み取った固定の語彙（kuroko-api の `LIKED`・`CONCERNS`）の呼び方
const VOCAB_LABEL: Record<string, string> = {
  food: "料理",
  atmosphere: "雰囲気",
  private_room: "個室",
  access: "行きやすさ",
  price: "価格",
  service: "接客",
  drinks: "飲み物",
  noisy: "騒がしさ",
  slow_service: "提供の遅さ",
  pricey: "割高",
  small: "狭さ",
  access_far: "駅から遠い",
  food_quality: "料理の質",
  other: "その他",
};

function CountBars({ title, counts }: { title: string; counts: Record<string, number> }) {
  const top = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);
  if (top.length === 0) return null;
  const max = Math.max(...top.map(([, n]) => n));
  return (
    <div className={styles.rows}>
      <span className={styles.meta}>{title}</span>
      {top.map(([key, n]) => (
        <div key={key} className={styles.barRow}>
          <span>{VOCAB_LABEL[key] ?? key}</span>
          <Progress value={n} max={max} label={`${VOCAB_LABEL[key] ?? key} ${n}件`} markDone={false} />
          <span className={styles.meta}>{n}件</span>
        </div>
      ))}
    </div>
  );
}

/**
 * 振り返りの集計と、KUROKO が次回に覚えること（SPEC 7.4・9.8）。個人ごとの回答は出さない。
 * 覚えさせる文は編集できない（含める・含めないと、「次回も使いたいか」だけを選ぶ）。
 */
function RetroCard({ id, retro, onDone, run }: FormProps & { retro: ApiRetro }) {
  const [reuse, setReuse] = useState<"yes" | "no" | "unanswered">("unanswered");
  const [include, setInclude] = useState<Record<string, boolean>>({ venue_record: true, venue_evaluation: true });
  const [busy, act] = useBusy();
  const pill = RETRO_PILL[retro.status];
  const decide = (decision: "save" | "skip") =>
    act(() =>
      run(async () => {
        await confirmRetro(id, {
          reuse_intent: reuse,
          include: retro.memory_facts.filter((f) => include[f.kind]).map((f) => f.kind),
          decision,
        });
        await onDone();
      }),
    );
  const saved = retro.memory_facts.filter((f) => f.saved);
  return (
    <KurokoRow card>
      <div className={styles.cardHead}>
        <span className={styles.cardTitle}>振り返り</span>
        <Pill tone={pill.tone}>{pill.label}</Pill>
      </div>
      <span>
        出席者の全員（{retro.invited_count}名）に、満足度（1〜5）をたずねました。個人ごとの回答は、幹事にも
        見えません。集計だけを使います。
      </span>
      <div className={styles.stats}>
        <div className={styles.statBox}>
          <span className={styles.meta}>回答</span>
          <span className={styles.statValue}>
            {retro.response_count}
            <span className={styles.statUnit}>/ {retro.invited_count}名</span>
          </span>
        </div>
        <div className={styles.statBox}>
          <span className={styles.meta}>満足度の平均</span>
          <span className={styles.statValue}>
            {retro.avg_rating !== null ? retro.avg_rating.toFixed(1) : "—"}
            <span className={styles.statUnit}>/ 5</span>
          </span>
        </div>
      </div>
      <Progress value={retro.response_count} max={retro.invited_count} label="振り返りの回答の数" />
      {retro.status !== "collecting" && (
        <>
          <CountBars title="良かった点（コメントから読み取った件数）" counts={retro.liked_counts} />
          <CountBars title="気になった点" counts={retro.concern_counts} />
          {retro.venue_name && retro.per_person_yen !== null && (
            <dl className={styles.facts}>
              <dt>お店</dt>
              <dd>{retro.venue_name}</dd>
              <dt>実績</dt>
              <dd>
                {retro.party_size}名・1人あたり {retro.per_person_yen.toLocaleString()}円（予算
                {retro.within_budget ? "内" : "超過"}）
              </dd>
            </dl>
          )}
        </>
      )}
      {retro.status === "collecting" && (
        <>
          <Caption>
            まだ答えていない方の回答を待っています。待たずに進めるときは、ここで締め切れます（その時点の回答で
            集計します）。
          </Caption>
          <div className={styles.actions}>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                void act(() =>
                  run(async () => {
                    await closeRetro(id);
                    await onDone();
                  }),
                )
              }
            >
              {busy ? "送信中…" : "回答を締め切る"}
            </Button>
          </div>
        </>
      )}
      {retro.status === "awaiting_organizer" && (
        <>
          <fieldset className={styles.group}>
            <legend>次回も、このお店を使いたいですか</legend>
            <div className={styles.choices}>
              {(
                [
                  ["yes", "はい"],
                  ["no", "いいえ"],
                  ["unanswered", "答えない"],
                ] as const
              ).map(([value, label]) => (
                <label key={value} className={styles.choice}>
                  <input type="radio" name={`reuse-${id}`} checked={reuse === value} onChange={() => setReuse(value)} />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className={styles.group}>
            <legend>KUROKO が、次回のために覚えること（外したいものは、チェックを外します）</legend>
            <div className={styles.rows}>
              {retro.memory_facts.map((f) => (
                <label key={f.kind} className={styles.fact}>
                  <input
                    type="checkbox"
                    checked={include[f.kind] ?? false}
                    onChange={(e) => setInclude((p) => ({ ...p, [f.kind]: e.target.checked }))}
                  />
                  <span>
                    <strong>{FACT_LABEL[f.kind]}</strong>：{f.text}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <Caption>
            覚える文は決まった形で、編集できません。個人名・個人ごとの回答は入りません。お金の計算には使いません。
          </Caption>
          <div className={styles.actions}>
            <Button onClick={() => void decide("save")} disabled={busy}>
              {busy ? "送信中…（記憶に保存しています）" : "次回に覚えさせる"}
            </Button>
            <Button variant="secondary" onClick={() => void decide("skip")} disabled={busy}>
              覚えさせない
            </Button>
          </div>
        </>
      )}
      {retro.status === "saved" && (
        <>
          <span className={styles.done}>次の内容を、記憶（Memory Bank）に保存しました。</span>
          <div className={styles.rows}>
            {saved.map((f) => (
              <div key={f.kind} className={styles.fact}>
                <span>
                  <strong>{FACT_LABEL[f.kind]}</strong>：{f.text}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
      {retro.status === "skipped" && <span>この会の内容は、記憶に保存していません。</span>}
    </KurokoRow>
  );
}

// ------------------------------------------------------------------ デモの終わり
/** すべて終わったことを、ひと目で分かるように出す（SPEC 7.7） */
function Finale({ detail, onRestart }: { detail: ApiEventDetail; onRestart: () => void }) {
  const total = detail.total_amount_yen;
  return (
    <div className={styles.finale} role="status">
      <span className={styles.finaleMark} aria-hidden>
        ✓
      </span>
      <span className={styles.finaleTitle}>デモは、ここまでです。お疲れさまでした</span>
      <span>
        「{detail.title || "飲み会"}」（{formatDateTime(detail.datetime)}）の幹事の仕事が、すべて完了しました。
      </span>
      <ul className={styles.finaleList}>
        <li>依頼 → 出欠・委任 → お店選び → 予約 → 開催の案内</li>
        <li>
          領収書{total ? `（${total.toLocaleString()}円）` : ""} → 規程にもとづく按分 → 承認 → 振込 → 入金の確認
        </li>
        <li>振り返り →{detail.retro?.status === "saved" ? " 次回のための記憶を保存" : " 記憶は保存していません"}</li>
      </ul>
      <div className={styles.actions}>
        <Button onClick={onRestart}>最初からやり直す</Button>
      </div>
    </div>
  );
}
