"""KUROKO の構成図（SVG）を書き出す。

使い方（リポジトリのルートで）:
  python3 docs/diagrams/make_architecture.py "docs/diagrams/export/KUROKO_GoogleCloud構成図_v2.0.svg"
構成が変わったら、このファイルを直して書き出し直す（正は docs/ARCHITECTURE.md）。
"""
import sys
from html import escape

W, H = 1600, 1010
FONT = "'Noto Sans JP','Hiragino Sans','Yu Gothic',Meiryo,sans-serif"
NAVY, STEEL, LINE = "#141d2e", "#5a6478", "#c9ccd4"
out = []


def rect(x, y, w, h, fill, stroke=LINE, r=12, dash=None, sw=1.5):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')


def text(x, y, s, size=14, weight=400, fill=NAVY, anchor="start"):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')


def group(x, y, w, h, title, fill):
    rect(x, y, w, h, fill, r=16)
    text(x + 16, y + 26, title, 15, 700)


def node(x, y, w, h, title, lines, fill="#ffffff", stroke=NAVY):
    rect(x, y, w, h, fill, stroke)
    text(x + 12, y + 24, title, 14.5, 700)
    for i, s in enumerate(lines):
        text(x + 12, y + 44 + i * 17, s, 12, 400, STEEL)
    return (x, y, w, h)


def arrow(x1, y1, x2, y2, label="", dash=False, lx=None, ly=None, color=NAVY, anchor="middle"):
    d = ' stroke-dasharray="6 5"' if dash else ""
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.8" marker-end="url(#a)"{d}/>')
    if label:
        tx, ty = (lx if lx is not None else (x1 + x2) / 2), (ly if ly is not None else (y1 + y2) / 2 - 6)
        out.append(f'<text x="{tx}" y="{ty}" font-size="11.5" fill="{STEEL}" text-anchor="{anchor}" paint-order="stroke" stroke="#ffffff" stroke-width="4">{escape(label)}</text>')


def poly(points, label="", lx=0, ly=0, dash=False, anchor="middle"):
    d = ' stroke-dasharray="6 5"' if dash else ""
    pts = " ".join(f"{x},{y}" for x, y in points)
    out.append(f'<polyline points="{pts}" fill="none" stroke="{NAVY}" stroke-width="1.8" marker-end="url(#a)"{d}/>')
    if label:
        out.append(f'<text x="{lx}" y="{ly}" font-size="11.5" fill="{STEEL}" text-anchor="{anchor}" paint-order="stroke" stroke="#ffffff" stroke-width="4">{escape(label)}</text>')


text(40, 44, "KUROKO — システム構成図（Google Cloud）", 24, 700)
text(40, 70, "AI（Gemini）は、聞く・探す・調べる・説明するだけ。金額の計算・検査・署名・振込は、Cloud Run のコードと本人の操作が担う。", 13.5, 400, STEEL)

# ---- Google Cloud の外（左）----
node(40, 130, 200, 84, "幹事・審査員", ["ブラウザ（Web）", "依頼・確認・アップロード"], "#fff3d6")
node(40, 300, 200, 84, "参加者・承認者", ["Slack（DM のボタン）", "出欠・委任・承認"], "#fff3d6")
node(40, 800, 200, 84, "GitHub Actions", ["CI ／ main へのマージで", "デプロイ（WIF。鍵なし）"], "#f1f2f5", STEEL)

# ---- Google Cloud ----
rect(280, 96, 1040, 884, "#fbf9f4", LINE, 20)
text(300, 122, "Google Cloud（kuroko-509311 / us-central1）", 15, 700, STEEL)

group(300, 140, 300, 250, "入口", "#eef1f7")
node(316, 176, 268, 64, "Firebase Hosting ＋ Auth", ["Web の配信・Google ログイン"])
node(316, 252, 268, 60, "kuroko-dashboard", ["Cloud Run（公開）・Next.js"])
node(316, 322, 268, 58, "kuroko-gateway", ["Cloud Run（公開）・署名の検証だけ"])

group(300, 410, 300, 150, "非同期", "#eef1f7")
node(316, 442, 268, 52, "Cloud Tasks", ["Slack の操作・請求・振り返りの受け渡し"])
node(316, 500, 268, 52, "Cloud Scheduler", ["銀行の承認・入金の確認（1分ごと）"])

group(620, 140, 320, 420, "業務のコード（Cloud Run・非公開）", "#e0f8f3")
node(636, 176, 288, 132, "kuroko-api", ["按分・Policy Gate・請求の署名", "振り返り・記憶の読み書き", "規程・予約・領収書の読み取り", "エージェント用のツール（MCP 4つ）"])
node(636, 322, 288, 100, "payment-api", ["AP2 の委任状の署名と検証", "Policy Gate・振込の依頼", "入金の確認・領収書の署名"])
node(636, 436, 288, 108, "bank-adapter", ["銀行 API の窓口", "口座とトークンは、ここだけ", "デモ用の振込の代行"])

group(960, 140, 340, 420, "Agent Platform（AI）", "#fff3d6")
node(1004, 176, 280, 62, "Agent Gateway ＋ Model Armor", ["エージェントの入口・出口を検査"])
node(1004, 250, 280, 62, "kuroko-agent（Agent Runtime）", ["統括エージェント（ADK・Gemini）"])
node(1004, 324, 280, 62, "extract-agent（Agent Runtime）", ["自由記述を語彙に落とす・ツールなし"])
node(1004, 398, 280, 62, "Memory Bank", ["チームの宴会実績（定型の文だけ）"])
node(1004, 472, 134, 74, "Agent Registry", ["ツールの名簿"])
node(1150, 472, 134, 74, "Gemini", ["Vertex AI"])

group(300, 580, 1000, 150, "データ・鍵（実行用のサービスアカウントごとに権限を分ける）", "#eef1f7")
node(316, 616, 228, 100, "Firestore（default）", ["イベント・参加者・按分・承認", "支払い・振り返り・経緯"])
node(556, 616, 176, 100, "Firestore（bank）", ["口座の対応表", "bank-adapter だけ"])
node(744, 616, 176, 100, "Cloud Storage", ["予約画面・領収書", "（署名付き URL）"])
node(932, 616, 176, 100, "Cloud KMS", ["請求・委任状の", "署名鍵"])
node(1120, 616, 164, 100, "Secret Manager", ["Slack・地図・銀行の", "キーとトークン"])

group(300, 750, 1000, 210, "役割の境界（これ自体が、いちばんの安全策）", "#ffffff")
for i, s in enumerate([
    "・AI が決めないもの: 金額の計算、承認者、支払先、規程の値、委任状への署名、店の順位、振込の作成、「完了」の判断",
    "・AI が見ないもの: 実名、口座番号、銀行のトークン、署名鍵、個人ごとの回答",
    "・請求する側（kuroko-api）と支払う側（payment-api）が、互いを信用せず、別々に検査する（Policy Gate）",
    "・お金を動かす最後の一押しは、口座の持ち主が銀行で行う。完了にするのは、銀行の明細で入金を確認できたときだけ",
    "・記憶に入るのは、幹事が確かめた、決まった形の文だけ。規程は、エージェントがツールで条ごとに調べる（全文は渡さない）",
    "・エージェントのツールは4つ（イベントの概要・予算の確認・店の検索・規程の検索）。お金・承認・署名のツールは無い",
]):
    text(320, 800 + i * 27, s, 13.5)

# ---- Google Cloud の外（右）----
node(1360, 176, 200, 100, "駅すぱあと", ["全員が帰りやすい駅", "（所要時間の検索）"], "#f1f2f5", STEEL)
node(1360, 300, 200, 84, "Google Maps", ["店の検索", "（Places API）"], "#f1f2f5", STEEL)
node(1360, 436, 200, 108, "sunabar", ["GMOあおぞらネット銀行の", "銀行 API（実験用の環境）", "振込依頼・本人承認・明細"], "#f1f2f5", STEEL)
node(1360, 616, 200, 100, "参加者（口座の持ち主）", ["銀行のサイトで、", "振込ごとに承認する"], "#fff3d6")

# ---- 線 ----
arrow(240, 172, 316, 200, "HTTPS", lx=276, ly=174)
arrow(450, 240, 450, 252)
arrow(584, 282, 636, 250, "API", lx=606, ly=256)
arrow(240, 342, 316, 350, "ボタン操作", lx=278, ly=334)
arrow(450, 380, 450, 442)
arrow(584, 468, 636, 296, "OIDC", lx=606, ly=420)
arrow(584, 526, 636, 404, "定期", lx=606, ly=500)
arrow(780, 308, 780, 322, "請求（署名つき）", lx=852, ly=319)
arrow(780, 422, 780, 436, "振込の依頼", lx=836, ly=433)
arrow(924, 204, 1004, 204, "依頼", lx=964, ly=198)
arrow(1144, 238, 1144, 250)
poly([(1004, 290), (964, 290), (964, 250), (924, 250)], "ツール（MCP）", 968, 243, dash=True)
arrow(924, 280, 1004, 352, "抽出", lx=972, ly=344)
arrow(924, 296, 1004, 428, "記憶", lx=972, ly=412)
# 外部 API（Agent Platform の枠の上を回る）
poly([(860, 176), (860, 131), (1340, 131), (1340, 226), (1360, 226)], "外部 API（駅・地図）。キーは Secret Manager", 1100, 127)
poly([(1340, 226), (1340, 342), (1360, 342)])
# 銀行（Agent Platform の枠の下を回る）
poly([(924, 520), (944, 520), (944, 570), (1340, 570), (1340, 490), (1360, 490)], "振込依頼・承認の状況・明細の照会", 1140, 566)
arrow(1460, 616, 1460, 544, "承認", lx=1486, ly=586)
arrow(780, 544, 780, 616)
arrow(240, 842, 300, 842, "デプロイ", lx=270, ly=832)

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">'
    '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{NAVY}"/></marker></defs>'
    f'<rect width="{W}" height="{H}" fill="#ffffff"/>' + "".join(out) + "</svg>"
)
open(sys.argv[1], "w", encoding="utf-8").write(svg)
