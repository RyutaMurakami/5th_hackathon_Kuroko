import { TaskBoard } from "@/components/TaskBoard";
import { aiTasks, humanTasks } from "@/lib/dev-docs";

const GROUP_NAMES: Record<string, string> = {
  E: "E. 環境準備",
  I: "I. インフラ",
  F: "F. フロントエンド",
  B: "B. バックエンド・AI",
  O: "O. 検証・その他",
};

export default function DevTasksPage() {
  return <TaskBoard ai={aiTasks()} human={humanTasks()} groupNames={GROUP_NAMES} />;
}
