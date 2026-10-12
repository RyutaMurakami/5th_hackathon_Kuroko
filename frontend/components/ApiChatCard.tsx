"use client";

// 実 API のチャット（検証用。最終的には Slack に統合する。SPEC 7.5）。
import { useEffect, useState } from "react";
import { errorText, sendMessage } from "@/lib/api-client";
import type { ChatMessage } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";
import { Card, ErrorBanner } from "./ui";

export function ApiChatCard({
  eventId,
  messages,
  onSent,
}: {
  eventId: string;
  messages: ChatMessage[];
  onSent: () => void;
}) {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 返答は別に作られる（pending）。できるまで「考え中」を出し、読み直し続ける
  const waiting = messages.some((m) => m.status === "pending");
  const thinking = sending || waiting;
  useEffect(() => {
    if (!waiting) return;
    const t = setInterval(onSent, 3000);
    return () => clearInterval(t);
  }, [waiting, onSent]);
  return (
    <Card title="KUROKO に相談する" description="検証用のチャットです。最終的には Slack で行います">
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <ChatPanel
        bare
        title=""
        messages={messages.filter((m) => m.status !== "pending")}
        thinking={thinking}
        onSend={(text) => {
          setSending(true);
          setError(null);
          sendMessage(text, eventId).then(
            () => {
              setSending(false);
              onSent();
            },
            (e) => {
              setSending(false);
              setError(errorText(e));
            },
          );
        }}
      />
    </Card>
  );
}
