"use client";

// 段階ごとの入力フォーム（計画・店・予約・領収書）。実 API につなぐ。検証用の画面とイベント詳細で共通。
// 委任・承認・振込の操作は置かない（Slack・銀行で行う）。
import { useState } from "react";
import {
  confirmBudgetOverrun,
  confirmExtraction,
  confirmPlan,
  markHeld,
  selectVenue,
  uploadFile,
} from "@/lib/api-client";
import type { ApiEventDetail } from "@/lib/api-types";
import { Button, Caption, Card } from "./ui";
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
      {(s === "rsvp" || s === "venue") && <VenueForm id={id} onDone={onDone} run={run} />}
      {s === "venue" && (
        <ReservationForm id={id} example={ex.reservation} onDone={onDone} run={run} />
      )}
      {s === "venue" && detail.budget_overrun && (
        <BudgetOverrunCard id={id} over={detail.budget_overrun} onDone={onDone} run={run} />
      )}
      {s === "booked" && <HeldCard id={id} onDone={onDone} run={run} />}
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
      </div>
      <ul className={styles.uploadList}>
        {detail.uploads.map((u) => (
          <li key={u.upload_id}>
            {u.kind === "receipt" ? "領収書" : "予約画面"}：{u.status}（読み取り：{u.extraction_status}）
          </li>
        ))}
      </ul>
      {reading && (
        <Caption>
          読み取り結果：{reading.venue_name ?? "店名不明"}／{reading.date ?? "日付不明"}／合計{" "}
          {reading.total_amount_yen?.toLocaleString()}円（明細 {reading.line_items.length}件）。
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
