// データの取り方の切り替え。`NEXT_PUBLIC_DATA_SOURCE=api` で実 API（/api/dashboard/*）、
// それ以外はダミー（lib/mock-data.ts）。ビルド時に決まる。
export const USE_API = process.env.NEXT_PUBLIC_DATA_SOURCE === "api";
