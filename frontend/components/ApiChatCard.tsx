"use client";

// 実 API のチャット（検証用。最終的には Slack に統合する。SPEC 7.5）。
import { useState } from "react";
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
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Card title="KUROKO に相談する" description="検証用のチャットです。最終的には Slack で行います">
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <ChatPanel
        bare
        title=""
        messages={messages}
        thinking={thinking}
        onSend={(text) => {
          setThinking(true);
          setError(null);
          sendMessage(text, eventId).then(
            () => {
              setThinking(false);
              onSent();
            },
            (e) => {
              setThinking(false);
              setError(errorText(e));
            },
          );
        }}
      />
    </Card>
  );
}
