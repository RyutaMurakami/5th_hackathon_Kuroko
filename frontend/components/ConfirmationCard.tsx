"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useState } from "react";
import { formatTime, formatYen } from "@/lib/format";
import { FADE_UP } from "@/lib/motion";
import type { Extraction, ExtractionField } from "@/lib/types";
import { Icon } from "./Icon";
import { Tabs, type TabItem } from "./Tabs";
import {
  PASTE_TEXT_ERROR,
  PasteZone,
  UploadDropzone,
  type UploadedFile,
  checkFile,
  imageFromClipboard,
} from "./UploadDropzone";
import { Button, Caption, Card, Chip, ErrorBanner, Pill, Progress, TextLink, uiStyles } from "./ui";
import styles from "./event.module.css";

type Phase = "upload" | "reading" | "failed" | "review" | "confirmed";
/** 入力元（SPEC 3章 Receipt.source）。予約情報だけ paste がある */
export type InputSource = "upload" | "paste" | "manual";
type Method = "file" | "paste" | "manual";

const COPY = {
  reservation: {
    eyebrow: "予約内容の確認",
    title: "予約画面を入れて、内容を確かめてください",
    manualTitle: "予約内容を手で入力してください",
    note: "確定すると、コース単価を規程の上限（1人 7,000円）と照らし合わせます。超えている場合は、予算超過の確認に進みます",
  },
  receipt: {
    eyebrow: "領収書の金額の確認",
    title: "領収書をアップロードして、金額を確かめてください",
    manualTitle: "領収書の金額を手で入力してください",
    note: "確定すると、承認者の按分の承認に進みます。承認は Slack で行われます",
  },
} as const;

// ダミーの読み取り時間（本番は ingest_reservation / ocr_receipt の結果を待つ）
const READING_MS = 1600;
// ダミー: 名前にこれらを含むファイルは「読み取れなかった」ことにする（手入力への切り替えを確かめるため）
const UNREADABLE = /fail|失敗|読取不可|unreadable/i;

const METHODS: TabItem<Method>[] = [
  { value: "file", label: "ファイル" },
  { value: "paste", label: "スクリーンショット" },
  { value: "manual", label: "手入力" },
];

function isEditable(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
}

/**
 * エージェントが読み取った結果（または手入力した値）を、幹事が見て、直して、確定する（DESIGN.md「Confirmation Card」）。
 * 予約情報は、ファイル・スクリーンショットの貼り付け・手入力の3つで入れる。領収書はアップロードだけで、
 * 読み取れなかったときに限って手入力できる（SPEC 7.5）。委任・承認・取り消し・振込の実行に当たる操作は置かない。
 */
export function ConfirmationCard({
  extraction,
  isGuest,
  onConfirmed,
}: {
  extraction: Extraction;
  isGuest: boolean;
  onConfirmed?: (source: InputSource) => void;
}) {
  const kind = extraction.kind;
  const copy = COPY[kind];
  const [phase, setPhase] = useState<Phase>(extraction.confirmedAt ? "confirmed" : "upload");
  const [method, setMethod] = useState<Method>("file");
  const [source, setSource] = useState<InputSource>("upload");
  const [file, setFile] = useState<UploadedFile | null>(null);
  const [uploads, setUploads] = useState(0);
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(extraction.fields.map((f) => [f.key, f.value])),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirmedAt, setConfirmedAt] = useState<string | null>(extraction.confirmedAt);
  const [zoom, setZoom] = useState(false);
  const [readProgress, setReadProgress] = useState(0);
  const [pasteError, setPasteError] = useState<string | null>(null);

  const original = Object.fromEntries(extraction.fields.map((f) => [f.key, f.value]));
  const manual = source === "manual";

  useEffect(() => {
    if (phase !== "reading") return;
    const started = Date.now();
    const timer = setInterval(() => {
      const ratio = Math.min(1, (Date.now() - started) / READING_MS);
      setReadProgress(ratio);
      if (ratio >= 1) {
        clearInterval(timer);
        setPhase(file && UNREADABLE.test(file.name) ? "failed" : "review");
      }
    }, 100);
    return () => clearInterval(timer);
  }, [phase, file]);

  const handleUploaded = (f: UploadedFile) => {
    setFile(f);
    setSource(f.via);
    setMethod(f.via === "paste" ? "paste" : "file");
    setUploads((n) => n + 1);
    setReadProgress(0);
    setPasteError(null);
    setPhase("reading");
  };

  // 予約情報が「入力待ち」のときは、ページのどこからでも Ctrl/⌘+V でスクリーンショットを貼り付けられる
  useEffect(() => {
    if (kind !== "reservation" || phase !== "upload") return;
    const onPaste = (e: ClipboardEvent) => {
      // 入力欄・チャットの入力中は、その入力欄に任せる。枠が自分で処理したものも二重にしない
      if (isEditable(e.target) || e.defaultPrevented) return;
      const image = imageFromClipboard(e.clipboardData);
      if (!image) {
        setPasteError(PASTE_TEXT_ERROR);
        setMethod("paste");
        return;
      }
      const problem = checkFile(image, kind, uploads);
      if (problem) {
        setPasteError(problem);
        setMethod("paste");
        return;
      }
      handleUploaded({ name: "貼り付けた画像", previewUrl: URL.createObjectURL(image), via: "paste" });
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [kind, phase, uploads]);

  /** 手入力に切り替える。値は空から（読み取りの値を持ち越さない） */
  const startManual = () => {
    setValues(Object.fromEntries(extraction.fields.map((f) => [f.key, ""])));
    setErrors({});
    setFile(null);
    setSource("manual");
    setMethod("manual");
    setPhase("review");
  };

  const backToUpload = (next: Method = "file") => {
    setValues(Object.fromEntries(extraction.fields.map((f) => [f.key, f.value])));
    setErrors({});
    setFile(null);
    setSource("upload");
    setMethod(next);
    setPasteError(null);
    setPhase("upload");
  };

  const chooseMethod = (next: Method) => {
    if (next === "manual") startManual();
    else backToUpload(next);
  };

  const confirm = () => {
    const next: Record<string, string> = {};
    for (const field of extraction.fields) {
      // 手入力でも、読み取りと同じ検査（空・型・範囲）を通す
      const message = validate(field, values[field.key] ?? "");
      if (message) next[field.key] = message;
    }
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    setConfirmedAt(new Date().toISOString());
    setPhase("confirmed");
    // 確定済みの表示を少し見せてから、段階を進める
    setTimeout(() => onConfirmed?.(source), 700);
  };

  // 予約情報は、確定するまで方法のタブを出し続ける（読み取りの結果を見てから手入力に切り替えられるように）。領収書には出さない
  const showMethodTabs = kind === "reservation" && phase !== "confirmed";
  const title =
    phase === "confirmed"
      ? `${copy.eyebrow}（確定済み）`
      : phase === "review" && manual
        ? copy.manualTitle
        : copy.title;

  return (
    <Card
      eyebrow={copy.eyebrow}
      title={title}
      actions={
        phase === "confirmed" && confirmedAt ? (
          <Pill tone="lagoon">
            確定済み（幹事・{manual ? "手入力・" : ""}
            {formatTime(confirmedAt)}）
          </Pill>
        ) : undefined
      }
    >
      {showMethodTabs && (
        <div className={styles.methodTabs}>
          <Tabs items={METHODS} value={method} onChange={chooseMethod} label="予約情報の入れ方" size="sm" idPrefix="reservation-method" />
        </div>
      )}

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={phase === "confirmed" ? "review" : phase === "upload" ? `upload-${method}` : phase}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={FADE_UP}
        >
          {phase === "upload" &&
            (kind === "reservation" && method === "paste" ? (
              <PasteZone
                kind={kind}
                isGuest={isGuest}
                uploadedCount={uploads}
                onUploaded={handleUploaded}
                externalError={pasteError}
              />
            ) : (
              <UploadDropzone kind={kind} isGuest={isGuest} uploadedCount={uploads} onUploaded={handleUploaded} />
            ))}

          {phase === "reading" && (
            <div className={styles.reading} aria-live="polite">
              <span>
                <strong>{file?.name}</strong> を読み取っています…
              </span>
              <Progress value={Math.round(readProgress * 100)} max={100} label="読み取りの進み具合" />
            </div>
          )}

          {phase === "failed" && (
            <div className={styles.failedBox}>
              <ErrorBanner>
                <strong>読み取れませんでした</strong>（{file?.name}）。画像が小さい・ぼやけているなどの可能性があります。
                別の画像を試すか、値を手で入力してください。
              </ErrorBanner>
              <div className={styles.actions} style={{ marginTop: 0 }}>
                <Button variant="secondary" onClick={() => backToUpload("file")}>
                  別のファイルにする
                </Button>
                <Button onClick={startManual}>
                  <Icon name="edit" size="sm" />
                  手で入力する
                </Button>
              </div>
            </div>
          )}

          {(phase === "review" || phase === "confirmed") && (
            <div className={manual ? undefined : styles.confirmGrid}>
              {!manual && <Thumbnail file={file} fallbackName={extraction.fileName} onZoom={() => setZoom(true)} />}
              <div>
                {manual && (
                  <div className={styles.manualNote} style={{ marginBottom: "var(--spacing-16)" }}>
                    <Icon name="edit" size="sm" />
                    <span>
                      画像なしで、自分で入力します。読み取りと同じ検査を通ります。
                      {kind === "receipt" && "領収書の画像がないことは、経費精算の記録に残ります。"}
                    </span>
                  </div>
                )}
                <div className={styles.fields}>
                  {extraction.fields.map((field) => (
                    <FieldInput
                      key={field.key}
                      field={field}
                      value={values[field.key] ?? ""}
                      error={errors[field.key]}
                      edited={!manual && values[field.key] !== original[field.key]}
                      readOnly={phase === "confirmed"}
                      onChange={(v) => setValues((prev) => ({ ...prev, [field.key]: v }))}
                    />
                  ))}
                </div>
                {phase === "review" && (
                  <>
                    <Caption className={styles.cellNote}>{copy.note}</Caption>
                    <div className={styles.actions}>
                      <Button onClick={confirm}>この内容で確定する</Button>
                      {/* 領収書の手入力は読み取れなかったときだけなので、戻る先はファイル */}
                      {!(kind === "reservation" && manual) && (
                        <Button variant="secondary" onClick={() => backToUpload("file")}>
                          別のファイルにする
                        </Button>
                      )}
                      <TextLink href="https://slack.com/" external>
                        Slack で開く
                      </TextLink>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {zoom && file?.previewUrl && (
        <button type="button" className={styles.lightbox} onClick={() => setZoom(false)} aria-label="拡大を閉じる">
          {/* eslint-disable-next-line @next/next/no-img-element -- アップロードした画像の一時的な表示 */}
          <img src={file.previewUrl} alt={`${file.name} の拡大`} />
        </button>
      )}
    </Card>
  );
}

function Thumbnail({
  file,
  fallbackName,
  onZoom,
}: {
  file: UploadedFile | null;
  fallbackName: string;
  onZoom: () => void;
}) {
  if (file?.previewUrl) {
    return (
      <button type="button" className={styles.thumb} onClick={onZoom} aria-label={`${file.name} を拡大`}>
        {/* eslint-disable-next-line @next/next/no-img-element -- アップロードした画像の一時的な表示 */}
        <img src={file.previewUrl} alt="" />
      </button>
    );
  }
  return (
    <div className={styles.thumb} style={{ cursor: "default" }}>
      <Icon name="file" />
      <span>{file?.name ?? fallbackName}</span>
    </div>
  );
}

function FieldInput({
  field,
  value,
  error,
  edited,
  readOnly,
  onChange,
}: {
  field: ExtractionField;
  value: string;
  error?: string;
  edited: boolean;
  readOnly: boolean;
  onChange: (value: string) => void;
}) {
  const id = useId();
  const numeric = field.kind !== "text";
  return (
    <div className={uiStyles.field}>
      <label className={uiStyles.fieldLabel} htmlFor={id}>
        {field.label}
        {edited && <Chip>修正済み</Chip>}
      </label>
      {readOnly ? (
        <span className={styles.readonlyValue} id={id}>
          {field.kind === "yen" ? formatYen(Number(value)) : `${value}${field.unit ?? ""}`}
        </span>
      ) : (
        <>
          <div className={uiStyles.inputWrap}>
            <input
              id={id}
              className={[uiStyles.input, numeric ? uiStyles.inputNumber : "", error ? uiStyles.inputError : ""].join(" ")}
              value={value}
              placeholder={field.placeholder}
              inputMode={numeric ? "numeric" : undefined}
              aria-invalid={!!error}
              aria-describedby={error ? `${id}-error` : undefined}
              onChange={(e) => onChange(e.target.value)}
            />
            {field.unit && <span className={uiStyles.unit}>{field.unit}</span>}
          </div>
          {error && (
            <span className={uiStyles.fieldError} id={`${id}-error`}>
              {error}
            </span>
          )}
        </>
      )}
    </div>
  );
}

/** 画面での検査（空・範囲外）。読み取りも手入力も同じ。確定の正は API 側の検査（Policy Gate 6.1） */
function validate(field: ExtractionField, raw: string): string | null {
  const value = raw.trim();
  if (!value) return `${field.label}を入力してください`;
  if (field.kind === "text") return null;
  const n = Number(value.replace(/,/g, ""));
  if (!Number.isInteger(n) || n <= 0) return `${field.label}は 1 以上の整数で入力してください`;
  if (field.kind === "yen" && n > 1_000_000) return `${field.label}が大きすぎます（100万円まで）`;
  if (field.kind === "number" && n > 100) return `${field.label}は 100 以下にしてください`;
  return null;
}
