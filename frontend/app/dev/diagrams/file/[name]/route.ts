import { diagrams, readRepoFile } from "@/lib/dev-docs";

// ビルド時に静的なファイルにする（実行時に content/ を読まない）
export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return diagrams().map((d) => ({ name: d.id }));
}

export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const file = diagrams().find((d) => d.id === name);
  if (!file) return new Response("not found", { status: 404 });
  return new Response(readRepoFile(`diagrams/${file.file}`), {
    headers: { "Content-Type": "image/svg+xml; charset=utf-8" },
  });
}
