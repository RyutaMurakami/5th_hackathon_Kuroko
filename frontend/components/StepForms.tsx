"use client";

// 段階ごとの入力（計画・店・予約・領収書・振り返り）。チャットの流れの中に、KUROKO からの操作のカード
// として出す（必要な入力は、チャットの中で完結する。SPEC 7.5）。入力欄には、デモ用の候補を入れておく。
// 委任・承認・振込の操作は置かない（参加者・承認者の列、Slack、銀行で行う）。
import { useState } from "react";
import {
  closeRetro,
  confirmBudgetOverrun,
  confirmExtraction,
  confirmPlan,
  confirmRetro,
  findVenues,
  markHeld,
  selectVenue,
  uploadFile,
} from "@/lib/api-client";
import type { ApiEventDetail, ApiRetro, ApiSplit } from "@/lib/api-types";
import { Button, Caption, Card, Pill } from "./ui";
import styles from "./verify.module.css";

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

export function StepForms({
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
      {s === "venue" && <VenueForm id={id} detail={detail} onDone={onDone} run={run} />}
      {s === "venue" && (
        <ReservationForm id={id} example={ex.reservation} detail={detail} onDone={onDone} run={run} />
      )}
      {s === "venue" && detail.budget_overrun && (
        <BudgetOverrunCard id={id} over={detail.budget_overrun} onDone={onDone} run={run} />
      )}
      {s === "booked" && <HeldCard id={id} onDone={onDone} run={run} />}
      {(s === "day_of" || s === "receipt") && (
        <ReceiptForm id={id} example={ex.receipt} detail={detail} onDone={onDone} run={run} />
      )}
      {detail.split && <SplitCard split={detail.split} detail={detail} />}
      {detail.retro && <RetroCard id={id} retro={detail.retro} onDone={onDone} run={run} />}
    </>
  );
}

type FormProps = {
  id: string;
  onDone: () => Promise<void>;
  run: (fn: () => Promise<unknown>, done?: string) => Promise<boolean>;
};

/** 今日の19時（`datetime-local` の形）。入金の確認は開催日からの明細を見るので、通しの確認は今日で行う */
function todayAt19(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T19:00`;
}

function PlanForm({ id, example, onDone, run }: FormProps & { example?: Record<string, unknown> }) {
  const [v, setV] = useState({
    title: String(example?.title ?? ""),
    datetime: todayAt19(),
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

function VenueForm({ id, detail, onDone, run }: FormProps & { detail: ApiEventDetail }) {
  const [searching, setSearching] = useState(false);
  const [manual, setManual] = useState(false);
  const [name, setName] = useState("");
  const candidates = detail.venue_candidates;
  const chosen = typeof detail.venue?.place_id === "string" ? detail.venue.place_id : null;
  const yen = (n: number | null) => (n === null ? "—" : n.toLocaleString());
  return (
    <Card
      title="店を選ぶ"
      description="全員の最寄り駅からの帰りやすさと、希望、過去の実績（記憶）から、候補を出します。順位は、決まった手順のコードが決めます"
      actions={chosen ? <Pill tone="lagoon">選択済み</Pill> : undefined}
    >
      {candidates.length === 0 ? (
        <div className={styles.formActions}>
          <Button
            disabled={searching}
            onClick={() => {
              setSearching(true);
              void run(async () => {
                await findVenues(id);
                await onDone();
              }).finally(() => setSearching(false));
            }}
          >
            {searching ? "探しています…（30秒ほど）" : "店の候補を出す"}
          </Button>
        </div>
      ) : (
        <ul className={styles.venueList}>
          {candidates.map((c, i) => (
            <li key={c.place_id} className={c.place_id === chosen ? styles.venueChosen : undefined}>
              <div className={styles.venueHead}>
                <strong>
                  {i + 1}. {c.name}
                </strong>
                <Button
                  variant={c.place_id === chosen ? "secondary" : "primary"}
                  disabled={c.place_id === chosen}
                  onClick={() =>
                    void run(async () => {
                      await selectVenue(id, c.place_id, c.name);
                      await onDone();
                    }, `「${c.name}」を選びました。予約したら、予約の内容を確定してください。`)
                  }
                >
                  {c.place_id === chosen ? "選択中" : "この店にする"}
                </Button>
              </div>
              <span className={styles.splitMeta}>
                {c.nearest_station}駅・最も遠い方で {c.max_travel_minutes}分（平均 {c.avg_travel_minutes}分）・1人{" "}
                {yen(c.price_min_yen)}〜{yen(c.price_max_yen)}円
              </span>
              <span>{c.selection_reason}</span>
              {c.memory_note && (
                <span className={styles.memoryNote}>
                  <Pill tone="sun">記憶</Pill> {c.memory_note}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {candidates.length > 0 && <Caption>アレルゲンは、店に確認してください。予約は、幹事が店で行います。</Caption>}
      {manual ? (
        <div className={styles.form}>
          <Field label="店の名前（候補に無い店）" value={name} onChange={setName} />
          <div className={styles.formActions}>
            <Button
              variant="secondary"
              onClick={() =>
                void run(async () => {
                  await selectVenue(id, `manual-${name}`, name);
                  await onDone();
                }, "店を選びました。")
              }
            >
              この店にする
            </Button>
          </div>
        </div>
      ) : (
        <button type="button" className={styles.sampleLink} onClick={() => setManual(true)}>
          候補に無い店を、名前で入れる
        </button>
      )}
    </Card>
  );
}

/** ISO の日時を、`datetime-local` の入力欄の形（その端末の時刻）にする */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function SampleLink({ href, children }: { href: string; children: string }) {
  return (
    <a className={styles.sampleLink} href={href} download>
      {children}
    </a>
  );
}

function ReservationForm({
  id,
  example,
  detail,
  onDone,
  run,
}: FormProps & { example?: Record<string, unknown>; detail: ApiEventDetail }) {
  const [v, setV] = useState({
    venue: String(example?.venue_name ?? ""),
    datetime: "",
    party: String(example?.party_size ?? ""),
    price: String(example?.course_price_yen ?? ""),
  });
  const set = (k: keyof typeof v) => (x: string) => setV((p) => ({ ...p, [k]: x }));
  const uploads = detail.uploads.filter((u) => u.kind === "reservation");
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
  const confirm = (source: "extracted" | "manual") =>
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
        source,
      );
      await onDone();
    }, "予約の内容を確定しました。");
  return (
    <Card
      title="予約の内容を確定する"
      description="店で予約したあと、予約完了の画面（画像・PDF）をアップロードすると、KUROKO が読み取ります。手入力もできます"
    >
      <div className={styles.uploadRow}>
        <input
          type="file"
          accept="image/jpeg,image/png,application/pdf"
          aria-label="予約画面のファイル"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f)
              void run(async () => {
                await uploadFile(id, "reservation", f);
                await onDone();
              }, "アップロードしました。読み取った内容を確かめてください。");
          }}
        />
        <SampleLink href="/samples/reservation_sample.png">サンプルの予約画面をダウンロード</SampleLink>
      </div>
      {reading && (
        <Caption>
          読み取り結果を入力欄に入れました。内容を確かめて、直すところがあれば直してください。
          {reading.warnings.length > 0 && ` 注意：${reading.warnings.join("、")}`}
        </Caption>
      )}
      {failed && <Caption>読み取れませんでした。手入力で確定できます。</Caption>}
      <div className={styles.form}>
        <Field label="店名" value={v.venue} onChange={set("venue")} />
        <Field label="日時" type="datetime-local" value={v.datetime} onChange={set("datetime")} />
        <Field label="人数" type="number" value={v.party} onChange={set("party")} />
        <Field label="コース単価（円）" type="number" value={v.price} onChange={set("price")} />
        <div className={styles.formActions}>
          {reading && <Button onClick={() => confirm("extracted")}>読み取った内容で確定する</Button>}
          <Button variant={reading ? "secondary" : "primary"} onClick={() => confirm("manual")}>
            {reading ? "手入力として確定する" : "この内容で確定する"}
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
  const read = [...detail.uploads].reverse().find((u) => u.kind === "receipt" && u.extraction) ?? null;
  const reading = read?.extraction ?? null;
  const [seeded, setSeeded] = useState<string | null>(null);
  // 読み取れた金額を入力欄に入れる（幹事が見て直せる）
  if (read && reading?.total_amount_yen && seeded !== read.upload_id) {
    setSeeded(read.upload_id);
    setAmount(String(reading.total_amount_yen));
  }
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
        <SampleLink href="/samples/receipt_sample.png">サンプルの領収書をダウンロード</SampleLink>
      </div>
      <ul className={styles.uploadList}>
        {detail.uploads
          .filter((u) => u.kind === "receipt")
          .map((u) => (
            <li key={u.upload_id}>
              領収書：{u.status}（読み取り：{u.extraction_status}）
            </li>
          ))}
      </ul>
      {reading && (
        <Caption>
          読み取り結果：{reading.venue_name ?? "店名不明"}／{reading.date ?? "日付不明"}／合計{" "}
          {reading.total_amount_yen?.toLocaleString()}円（明細 {reading.line_items?.length ?? 0}件）。
          {reading.warnings.length > 0 && ` 注意：${reading.warnings.join("、")}`}
        </Caption>
      )}
      <div className={styles.form}>
        <Field label="合計金額（円）" type="number" value={amount} onChange={setAmount} />
        <div className={styles.formActions}>
          {reading && (
            <Button
              onClick={() =>
                void run(async () => {
                  await confirmExtraction(id, "receipt", { total_amount_yen: Number(amount) }, "extracted");
                  await onDone();
                }, "金額を確定しました。按分に進みます。")
              }
            >
              この金額で確定する
            </Button>
          )}
          <Button
            variant="secondary"
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
      {!failed && !reading && <Caption>アップロードすると、金額を読み取って、ここに出します。</Caption>}
    </Card>
  );
}


function BudgetOverrunCard({
  id,
  over,
  onDone,
  run,
}: FormProps & { over: NonNullable<ApiEventDetail["budget_overrun"]> }) {
  return (
    <Card
      title="予算超過の確認"
      description={`コース単価 ${over.course_price_yen.toLocaleString()}円が、規程の上限 ${over.limit_yen.toLocaleString()}円を超えています。続行するか、幹事が確認します。そのあと承認者に最終確認が Slack で届きます。`}
    >
      {over.organizer_confirmed ? (
        <Caption>
          幹事の確認は済みました。承認者の最終確認（Slack）を待っています。
        </Caption>
      ) : (
        <Button
          onClick={() =>
            void run(async () => {
              await confirmBudgetOverrun(id);
              await onDone();
            }, "予算超過での続行を確認しました。承認者に最終確認を依頼しています。")
          }
        >
          超過を確認して続行する
        </Button>
      )}
    </Card>
  );
}

function HeldCard({ id, onDone, run }: FormProps) {
  return (
    <Card title="開催後の操作" description="開催が終わったら押してください。領収書のアップロードに進みます">
      <Button
        onClick={() =>
          void run(async () => {
            await markHeld(id);
            await onDone();
          }, "開催の終了を記録しました。領収書をアップロードしてください。")
        }
      >
        開催が終わった
      </Button>
    </Card>
  );
}

// 規程の値のまとまり（kuroko-api の `citations` の鍵）の呼び方
const CITATION_LABEL: Record<string, string> = {
  member_classes: "負担係数",
  subsidy: "会社の補助",
  rounding: "端数の扱い",
  approver: "承認者の決め方",
};

/** 按分の内訳（保存された値をそのまま出す。画面で再計算しない）と、根拠の規程（SPEC 7.3.1・9.7） */
function SplitCard({ split, detail }: { split: ApiSplit; detail: ApiEventDetail }) {
  const name = (id: string) => detail.participants.find((p) => p.user_id === id)?.display_name ?? id;
  const cited = Object.entries(CITATION_LABEL)
    .filter(([k]) => split.policy?.citations[k])
    .map(([k, label]) => `${label}は${split.policy?.citations[k]}`);
  return (
    <Card
      title="按分の内訳"
      description={`会計 ${split.total_amount_yen.toLocaleString()}円 − 会社補助 ${split.subsidy_yen.toLocaleString()}円 = 按分の対象額 ${split.base_amount_yen.toLocaleString()}円`}
      actions={
        <Pill tone={split.approval.status === "approved" ? "lagoon" : "sun"}>
          {split.approval.status === "approved" ? "承認済み" : `承認待ち（${name(split.approval.approver_user_id)}）`}
        </Pill>
      }
    >
      <ul className={styles.splitList}>
        {split.rows.map((r) => (
          <li key={r.user_id}>
            <span>{name(r.user_id)}</span>
            <span className={styles.splitMeta}>
              {r.weight === 0 ? "主役（負担なし）" : `係数 ${r.weight}・${r.ratio_percent.toFixed(2)}%`}
            </span>
            <span className={styles.splitYen}>{r.share_yen.toLocaleString()}円</span>
          </li>
        ))}
      </ul>
      <Caption>
        計算は、決まった手順のコードが行いました（AI は金額を計算しません）。
        {split.policy?.source === "document"
          ? ` 値は、規程の文書（懇親会費用規程）から AI が読み取り、コードが検証したものです。${cited.join("、")}。`
          : " 規程の値は、既定の値を使っています。"}
      </Caption>
    </Card>
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

/**
 * 振り返りの集計と、KUROKO が次回に覚えること（SPEC 7.4・9.8）。個人ごとの回答は出さない。
 * 覚えさせる文は編集できない（含める・含めないと、「次回も使いたいか」だけを選ぶ）。
 */
function RetroCard({ id, retro, onDone, run }: FormProps & { retro: ApiRetro }) {
  const [reuse, setReuse] = useState<"yes" | "no" | "unanswered">("unanswered");
  const [include, setInclude] = useState<Record<string, boolean>>({ venue_record: true, venue_evaluation: true });
  const pill = RETRO_PILL[retro.status];
  const decide = (decision: "save" | "skip") =>
    void run(
      async () => {
        await confirmRetro(id, {
          reuse_intent: reuse,
          include: retro.memory_facts.filter((f) => include[f.kind]).map((f) => f.kind),
          decision,
        });
        await onDone();
      },
      decision === "save" ? "次回のために、記憶に保存しました。" : "保存せずに終えました。",
    );
  return (
    <Card
      title="振り返りと、KUROKO が覚えること"
      description="個人ごとの回答は、幹事にも見えません。集計だけを使います"
      actions={<Pill tone={pill.tone}>{pill.label}</Pill>}
    >
      <ul className={styles.retroStats}>
        <li>
          回答 <strong>{retro.response_count}</strong> / {retro.invited_count}名
        </li>
        <li>
          満足度の平均 <strong>{retro.avg_rating !== null ? retro.avg_rating.toFixed(1) : "—"}</strong> / 5
        </li>
        {retro.venue_name && retro.per_person_yen !== null && (
          <li>
            実績（自動の記録）：{retro.venue_name}・{retro.party_size}名・1人あたり{" "}
            {retro.per_person_yen.toLocaleString()}円（予算{retro.within_budget ? "内" : "超過"}）
          </li>
        )}
      </ul>
      {retro.status === "collecting" && (
        <div className={styles.formActions}>
          <Caption>参加者の回答を待っています。待たずに進めるときは、ここで締め切れます。</Caption>
          <Button
            variant="secondary"
            onClick={() =>
              void run(async () => {
                await closeRetro(id);
                await onDone();
              }, "回答を締め切りました。内容を確認してください。")
            }
          >
            回答を締め切る
          </Button>
        </div>
      )}
      {retro.status === "awaiting_organizer" && (
        <>
          <fieldset className={styles.retroQuestion}>
            <legend>次回も、この店を使いたいですか</legend>
            {(
              [
                ["yes", "はい"],
                ["no", "いいえ"],
                ["unanswered", "答えない"],
              ] as const
            ).map(([value, label]) => (
              <label key={value}>
                <input type="radio" name="reuse" checked={reuse === value} onChange={() => setReuse(value)} />
                {label}
              </label>
            ))}
          </fieldset>
          <ul className={styles.factList}>
            {retro.memory_facts.map((f) => (
              <li key={f.kind}>
                <label>
                  <input
                    type="checkbox"
                    checked={include[f.kind] ?? false}
                    onChange={(e) => setInclude((p) => ({ ...p, [f.kind]: e.target.checked }))}
                  />
                  <span>
                    <strong>{FACT_LABEL[f.kind]}</strong>：{f.text}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <Caption>
            覚えさせる文は、決まった形の文で、編集できません。「次回も使いたいか」の答えは、保存するときに評価の文に入ります。
          </Caption>
          <div className={styles.formActions}>
            <Button onClick={() => decide("save")}>次回に覚えさせる</Button>
            <Button variant="secondary" onClick={() => decide("skip")}>
              覚えさせない
            </Button>
          </div>
        </>
      )}
      {(retro.status === "saved" || retro.status === "skipped") && (
        <>
          <ul className={styles.factList}>
            {retro.memory_facts
              .filter((f) => f.saved)
              .map((f) => (
                <li key={f.kind}>
                  <span>
                    <strong>{FACT_LABEL[f.kind]}</strong>：{f.text}
                  </span>
                </li>
              ))}
          </ul>
          <Caption>
            {retro.status === "saved"
              ? "上の内容を、記憶（Memory Bank）に保存しました。次の企画で、同じ店が候補に出たときに、理由に添えられます。"
              : "この会の内容は、記憶に保存していません。"}
          </Caption>
        </>
      )}
    </Card>
  );
}
