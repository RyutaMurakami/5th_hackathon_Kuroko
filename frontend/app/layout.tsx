import type { Metadata } from "next";
import { Inter, Noto_Sans_JP } from "next/font/google";
import { Suspense } from "react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { DemoToolbar } from "@/components/DemoToolbar";
import { GuestBanner } from "@/components/GuestBanner";
import { Providers } from "@/components/Providers";
import "./globals.css";

// 英数字は Inter、日本語は Noto Sans JP（DESIGN.md「Tokens — Typography」）
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-inter",
  display: "swap",
});

const notoSansJp = Noto_Sans_JP({
  weight: ["400", "500", "700"],
  variable: "--font-noto-sans-jp",
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  title: "KUROKO",
  description: "飲み会の幹事を、規程に沿って代行する AI エージェント",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className={`${inter.variable} ${notoSansJp.variable}`}>
      <body>
        <Providers>
          {/* 役割・段階は URL のクエリで持つので、useSearchParams を使う部分を Suspense で包む */}
          <Suspense>
            <AppHeader />
            <GuestBanner />
          </Suspense>
          <AuthGate>{children}</AuthGate>
          <Suspense>
            <DemoToolbar />
          </Suspense>
        </Providers>
      </body>
    </html>
  );
}
