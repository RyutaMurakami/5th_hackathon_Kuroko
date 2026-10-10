// ブラウザ → kuroko-dashboard（この中継）→ kuroko-api の `/api/dashboard/*`（ARCHITECTURE 4.5）。
// kuroko-api は非公開の Cloud Run なので、ブラウザから直接は呼べない。この中継が
//  ① Cloud Run の ID トークン（sa-dashboard。呼び出し元の確認）と
//  ② 利用者の Firebase の ID トークン（X-Firebase-Token。利用者の確認）を付けて渡す。
// 利用者の権限の判定は kuroko-api の側で行う（ここでは行わない）。設定が無ければ全て拒否する。
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const FORWARD_BODY = new Set(["POST"]);

async function serviceIdToken(audience: string): Promise<string | null> {
  // ローカルの開発では、用意した ID トークンを使う（`gcloud auth print-identity-token --audiences=...`）
  if (process.env.DASHBOARD_DEV_ID_TOKEN) return process.env.DASHBOARD_DEV_ID_TOKEN;
  try {
    const res = await fetch(
      `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${encodeURIComponent(audience)}`,
      { headers: { "Metadata-Flavor": "Google" }, cache: "no-store" },
    );
    return res.ok ? await res.text() : null;
  } catch {
    return null;
  }
}

async function relay(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const base = process.env.KUROKO_API_URL?.replace(/\/$/, "");
  if (!base) return NextResponse.json({ detail: "not_configured" }, { status: 503 });
  const { path } = await ctx.params;
  if (path.some((p) => p === ".." || p === "." || p.includes("/") || p.includes("\\"))) {
    return NextResponse.json({ detail: "bad_path" }, { status: 400 });
  }
  const firebaseToken = req.headers.get("x-firebase-token");
  if (!firebaseToken) return NextResponse.json({ detail: "unauthenticated" }, { status: 401 });
  const idToken = await serviceIdToken(base);
  if (!idToken) return NextResponse.json({ detail: "upstream_auth_failed" }, { status: 502 });

  const url = `${base}/api/dashboard/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const upstream = await fetch(url, {
    method: req.method,
    headers: {
      Authorization: `Bearer ${idToken}`,
      "X-Firebase-Token": firebaseToken,
      "Content-Type": "application/json",
    },
    body: FORWARD_BODY.has(req.method) ? await req.text() : undefined,
    cache: "no-store",
  });
  // 中身はそのまま返す（エラーの理由コードも含む）。上流のヘッダーは渡さない
  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
  });
}

export const GET = relay;
export const POST = relay;
