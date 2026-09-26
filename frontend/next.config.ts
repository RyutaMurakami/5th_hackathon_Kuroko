import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cloud Run 用に、実行に必要なファイルだけを .next/standalone にまとめる（ARCHITECTURE 4.5）
  output: "standalone",
  // 開発時の Next.js のインジケーターが Demo Toolbar と重なるので出さない
  devIndicators: false,
  // Pin the workspace root to this directory so Next.js doesn't misdetect it
  // from an unrelated lockfile elsewhere on the machine.
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
