import { VerifyView } from "@/components/VerifyView";

// 開発者の実演用の画面（Slack と本物の銀行 API で操作する。登録したアカウントだけ。SPEC 7.7）
export default function DemoPage() {
  return <VerifyView mode="live" />;
}
