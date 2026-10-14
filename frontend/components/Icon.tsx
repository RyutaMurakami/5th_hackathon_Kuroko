// 線画のアイコン（線の太さ 1.5px、16px / 20px。色は文字と同じ）。DESIGN.md「Imagery」。
// ライブラリは追加せず、使うものだけをここに置く。

type IconName =
  | "info"
  | "bell"
  | "arrowRight"
  | "check"
  | "slack"
  | "upload"
  | "file"
  | "chevronDown"
  | "user"
  | "send"
  | "download"
  | "alert"
  | "close"
  | "chat"
  | "clipboard"
  | "edit"
  | "image"
  | "map"
  | "plus"
  | "refresh"
  | "book";

const PATHS: Record<IconName, React.ReactNode> = {
  info: (
    <>
      <circle cx="10" cy="10" r="7.5" />
      <path d="M10 9v4.5M10 6.5v.01" />
    </>
  ),
  bell: (
    <>
      <path d="M5 13.5V9a5 5 0 0 1 10 0v4.5l1.5 1.5h-13L5 13.5Z" />
      <path d="M8.5 17a1.5 1.5 0 0 0 3 0" />
    </>
  ),
  arrowRight: <path d="M4 10h12M11.5 5.5 16 10l-4.5 4.5" />,
  plus: <path d="M10 4v12M4 10h12" />,
  refresh: (
    <>
      <path d="M16 10a6 6 0 1 1-1.8-4.3" />
      <path d="M16 3.5v3.5h-3.5" />
    </>
  ),
  book: (
    <>
      <path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H16v12H5.5A1.5 1.5 0 0 0 4 16.5v-12Z" />
      <path d="M4 16.5A1.5 1.5 0 0 0 5.5 18H16v-3" />
    </>
  ),
  check: <path d="m5 10.5 3.2 3L15 6.5" />,
  slack: (
    <>
      <rect x="3" y="8.5" width="6" height="3" rx="1.5" />
      <rect x="11" y="8.5" width="6" height="3" rx="1.5" />
      <rect x="8.5" y="3" width="3" height="6" rx="1.5" />
      <rect x="8.5" y="11" width="3" height="6" rx="1.5" />
    </>
  ),
  upload: (
    <>
      <path d="M10 13V3.5M6 7.5l4-4 4 4" />
      <path d="M3.5 13v2.5a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V13" />
    </>
  ),
  file: (
    <>
      <path d="M5 2.5h6.5L15 6v11.5H5z" />
      <path d="M11.5 2.5V6H15" />
    </>
  ),
  chevronDown: <path d="m5.5 8 4.5 4.5L14.5 8" />,
  user: (
    <>
      <circle cx="10" cy="7" r="3.5" />
      <path d="M3.5 17a6.5 6.5 0 0 1 13 0" />
    </>
  ),
  send: <path d="M3.5 10 16.5 3.5 13 16.5l-3-5-6.5-1.5Z" />,
  download: (
    <>
      <path d="M10 3.5V13M6 9l4 4 4-4" />
      <path d="M3.5 13v2.5a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V13" />
    </>
  ),
  close: <path d="m5.5 5.5 9 9M14.5 5.5l-9 9" />,
  chat: (
    <>
      <path d="M3.5 5.5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H9l-3.5 3v-3a2 2 0 0 1-2-2v-6Z" />
      <path d="M7 8.5h6" />
    </>
  ),
  clipboard: (
    <>
      <rect x="4.5" y="4" width="11" height="13" rx="1.5" />
      <path d="M7.5 4V3h5v1M7.5 9h5M7.5 12h5" />
    </>
  ),
  edit: <path d="M4 16h3l8.5-8.5-3-3L4 13v3ZM11 6l3 3" />,
  image: (
    <>
      <rect x="3" y="4" width="14" height="12" rx="2" />
      <circle cx="7.5" cy="8.5" r="1.2" />
      <path d="m4 14 3.5-3.5 3 3 2-2L16 15" />
    </>
  ),
  map: (
    <>
      <path d="M10 17s5-4.4 5-8.3A5 5 0 0 0 5 8.700c0 3.900 5 8.300 5 8.300Z" />
      <circle cx="10" cy="8.5" r="1.8" />
    </>
  ),
  alert: (
    <>
      <path d="M10 3 17.5 16.5h-15L10 3Z" />
      <path d="M10 8v4M10 14.2v.01" />
    </>
  ),
};

export function Icon({
  name,
  size = "md",
  label,
}: {
  name: IconName;
  size?: "sm" | "md";
  /** 文字なしで意味を伝えるときだけ付ける */
  label?: string;
}) {
  const px = size === "sm" ? "var(--icon-size-sm)" : "var(--icon-size)";
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ width: px, height: px, strokeWidth: "var(--icon-stroke)", flex: "none" }}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {PATHS[name]}
    </svg>
  );
}
