// 表示の書式（DESIGN.md「Tokens — Typography」）。金額は「3,300円」、日時は「10/30（金）19:00」。

const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];

export function formatYen(value: number): string {
  return `${value.toLocaleString("ja-JP")}円`;
}

/** 単位を別に添えるとき用（Stat Block など） */
export function formatNumber(value: number): string {
  return value.toLocaleString("ja-JP");
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}（${WEEKDAYS[d.getDay()]}）${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** タイムライン用の短い日時（10/30 19:00） */
export function formatShortDateTime(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatWeight(weight: number): string {
  return `×${weight.toFixed(1)}`;
}

/** アバターの頭文字（1文字） */
export function initialOf(name: string): string {
  return name.startsWith("User_") ? name.slice(-2) : name.slice(0, 1);
}
