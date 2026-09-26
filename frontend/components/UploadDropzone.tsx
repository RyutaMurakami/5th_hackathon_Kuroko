"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import { Button, Caption, ErrorBanner, TextButton } from "./ui";
import styles from "./event.module.css";

// SPEC 7.5「アップロードの条件」。画面でも検査するが、正は API 側の検査
const ACCEPT = ["image/jpeg", "image/png", "application/pdf"];
const MAX_BYTES = 5 * 1024 * 1024;
export const UPLOAD_LIMIT = { reservation: 2, receipt: 3 } as const;

export type UploadKind = keyof typeof UPLOAD_LIMIT;

export type UploadedFile = {
  name: string;
  previewUrl: string | null;
  /** ファイル（upload）か、スクリーンショットの貼り付け（paste）か */
  via: "upload" | "paste";
};

const NOUN: Record<UploadKind, string> = { reservation: "予約画面", receipt: "領収書" };

/** ファイルと貼り付けで共通の検査。問題があれば、種類・サイズ・件数を具体的に書いた文を返す */
export function checkFile(file: File, kind: UploadKind, uploadedCount: number): string | null {
  if (uploadedCount >= UPLOAD_LIMIT[kind]) {
    return `${NOUN[kind]}は1イベントあたり ${UPLOAD_LIMIT[kind]}件までです。`;
  }
  if (!ACCEPT.includes(file.type)) {
    return `「${file.name}」は読み取れない種類です。JPEG・PNG・PDF を選んでください。`;
  }
  if (file.size > MAX_BYTES) {
    const mb = (file.size / 1024 / 1024).toFixed(1);
    return `「${file.name}」は ${mb}MB です。1ファイル 5MB までにしてください。`;
  }
  return null;
}

function toUploaded(file: File, via: UploadedFile["via"]): UploadedFile {
  return {
    // クリップボードの画像は名前が "image.png" になるので、分かる名前にする
    name: via === "paste" ? "貼り付けた画像" : file.name,
    previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
    via,
  };
}

/** クリップボードのデータから、画像のファイルを1つ取り出す。なければ null */
export function imageFromClipboard(data: DataTransfer | null): File | null {
  if (!data) return null;
  for (const item of Array.from(data.items)) {
    if (item.kind === "file" && item.type.startsWith("image/")) return item.getAsFile();
  }
  return null;
}

export const PASTE_TEXT_ERROR = "画像を貼り付けてください。文字を貼り付けたい場合は、［手入力］タブから入力できます。";

/** 予約画面・領収書のファイルのアップロード（DESIGN.md「Upload Dropzone」） */
export function UploadDropzone({
  kind,
  isGuest,
  uploadedCount,
  onUploaded,
}: {
  kind: UploadKind;
  isGuest: boolean;
  uploadedCount: number;
  onUploaded: (file: UploadedFile) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const noun = NOUN[kind];

  const accept = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    if (files.length > 1) {
      setError("1回に選べるのは1ファイルです。");
      return;
    }
    const problem = checkFile(files[0], kind, uploadedCount);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    onUploaded(toUploaded(files[0], "upload"));
  };

  return (
    <div className={styles.composer}>
      <div
        className={`${styles.dropzone} ${dragging ? styles.dropzoneActive : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          accept(e.dataTransfer.files);
        }}
      >
        <Icon name="upload" />
        <p>ここに{noun}の画像・PDF をドロップ、または</p>
        <Button variant="secondary" onClick={() => inputRef.current?.click()}>
          ファイルを選ぶ
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT.join(",")}
          className="visually-hidden"
          tabIndex={-1}
          onChange={(e) => {
            accept(e.target.files);
            e.target.value = "";
          }}
        />
        <Caption>JPEG・PNG・PDF／1ファイル 5MB まで</Caption>
        {isGuest && <Caption>実在の個人情報や領収書を入れないでください</Caption>}
        {isGuest && (
          <div className={styles.dropzoneLinks}>
            <TextButton onClick={() => downloadSample(kind)}>
              <Icon name="download" size="sm" />
              サンプルの{noun}をダウンロード
            </TextButton>
          </div>
        )}
      </div>
      {error && <ErrorBanner>{error}</ErrorBanner>}
    </div>
  );
}

/**
 * スクリーンショットの貼り付け（予約情報だけ。DESIGN.md「Upload Dropzone」）。
 * この枠にフォーカスして Ctrl/⌘+V、またはボタンで貼り付ける。ページのどこからでも貼れるようにする処理は ConfirmationCard 側。
 */
export function PasteZone({
  kind,
  isGuest,
  uploadedCount,
  onUploaded,
  externalError,
}: {
  kind: UploadKind;
  isGuest: boolean;
  uploadedCount: number;
  onUploaded: (file: UploadedFile) => void;
  /** ページ全体の貼り付けで起きたエラー */
  externalError?: string | null;
}) {
  const [error, setError] = useState<string | null>(null);
  const [focused, setFocused] = useState(false);
  const zoneRef = useRef<HTMLDivElement>(null);

  const take = (file: File | null) => {
    if (!file) {
      setError(PASTE_TEXT_ERROR);
      return;
    }
    const problem = checkFile(file, kind, uploadedCount);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    onUploaded(toUploaded(file, "paste"));
  };

  const readClipboard = async () => {
    try {
      const items = await navigator.clipboard.read();
      for (const item of items) {
        const type = item.types.find((t) => t.startsWith("image/"));
        if (type) {
          const blob = await item.getType(type);
          take(new File([blob], "image.png", { type }));
          return;
        }
      }
      setError(PASTE_TEXT_ERROR);
    } catch {
      // 非対応・許可されなかったとき
      setError("クリップボードを読み取れませんでした。この枠をクリックして、Ctrl / ⌘ + V で貼り付けてください。");
      zoneRef.current?.focus();
    }
  };

  useEffect(() => {
    zoneRef.current?.focus();
  }, []);

  const shown = error ?? externalError ?? null;
  return (
    <div className={styles.composer}>
      <div
        ref={zoneRef}
        className={`${styles.dropzone} ${styles.pasteZone} ${focused ? styles.pasteZoneReady : ""}`}
        tabIndex={0}
        role="group"
        aria-label="スクリーンショットの貼り付け"
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onPaste={(e) => {
          e.preventDefault();
          take(imageFromClipboard(e.clipboardData));
        }}
      >
        <Icon name="clipboard" />
        <p>
          ここをクリックして、<kbd className={styles.kbd}>Ctrl / ⌘</kbd> + <kbd className={styles.kbd}>V</kbd> で貼り付け
        </p>
        <Button variant="secondary" onClick={readClipboard}>
          クリップボードから貼り付ける
        </Button>
        <Caption>スクリーンショットをコピーしてから貼り付けてください（JPEG・PNG／5MB まで）</Caption>
        {isGuest && <Caption>実在の個人情報を入れないでください</Caption>}
      </div>
      {shown && <ErrorBanner>{shown}</ErrorBanner>}
    </div>
  );
}

/** 審査員向けのサンプル（架空）。画面の中で PNG を描いて保存させる */
function downloadSample(kind: UploadKind) {
  const canvas = document.createElement("canvas");
  canvas.width = 480;
  canvas.height = 640;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const styles = getComputedStyle(document.documentElement);
  const ink = styles.getPropertyValue("--color-ink-navy").trim();
  const paper = styles.getPropertyValue("--color-pure-white").trim();
  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = ink;
  const lines =
    kind === "receipt"
      ? ["領 収 書（サンプル）", "", "炉端 こだま 神田店", "2026/10/30", "", "コース 5,500円 × 10名", "追加のドリンク 5,300円", "", "合計 60,300円", "", "※ 架空のサンプルです"]
      : ["ご予約完了（サンプル）", "", "炉端 こだま 神田店", "10/30（金）19:00", "10名さま", "宴会コース 5,500円", "", "※ 架空のサンプルです"];
  lines.forEach((line, i) => {
    ctx.font = i === 0 ? "bold 28px sans-serif" : "22px sans-serif";
    ctx.fillText(line, 40, 80 + i * 44);
  });
  const link = document.createElement("a");
  link.download = kind === "receipt" ? "sample_receipt.png" : "sample_reservation.png";
  link.href = canvas.toDataURL("image/png");
  link.click();
}
