"use client";

import { AnimatePresence, motion } from "motion/react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useDemoHref, useDemoRole, useDemoStage } from "@/lib/demo";
import { useEventDetail } from "@/lib/data";
import { USE_API } from "@/lib/data-source";
import type { ApiEventDetail } from "@/lib/api-types";
import { FADE_UP, STAGGER } from "@/lib/motion";
import { CONSENT_STATE } from "@/lib/status";
import type { EventDetail, EventStatus, Role } from "@/lib/types";
import { ApiChatCard } from "./ApiChatCard";
import { ScenarioHint } from "./ScenarioHint";
import { ConfirmationCard, type InputSource } from "./ConfirmationCard";
import { ConsentList } from "./ConsentList";
import { DecisionTimeline } from "./DecisionTimeline";
import { EventSummary } from "./EventSummary";
import { KurokoDock } from "./KurokoDock";
import { PaymentTable } from "./PaymentTable";
import { RetroSummaryCard, type RetroDecision } from "./RetroSummaryCard";
import { SplitTable } from "./SplitTable";
import { Tabs, type TabItem } from "./Tabs";
import { type ToastInput, useToast } from "./Toast";
import { VenueChoiceCard } from "./VenueChoiceCard";
import { Card, EmptyState, InfoBanner, TextLink } from "./ui";
import detail from "./detail.module.css";
import styles from "./event.module.css";

type DetailTab = "payments" | "split" | "retro" | "log";
const TABS: DetailTab[] = ["payments", "split", "retro", "log"];

/** 最初に選ばれるタブは段階に合わせる（DESIGN.md「Tab Pill Navigation」） */
function defaultTab(status: EventStatus): DetailTab {
  if (status === "split" || status === "approval") return "split";
  if (status === "retro" || status === "closed") return "retro";
  return "payments";
}

type AutoStep = { next: EventStatus; delay: number; toast: Omit<ToastInput, "eventId">; guestOnly: boolean };

/**
 * ダミーで段階を自動で進める場面。按分の計算（システム）は全員、
 * Slack で人が行う部分と日付の早送りは、ゲストの体験用イベントだけ（デモ用の代行。SPEC 7.6 の (A)）。
 */
const AUTO: Partial<Record<EventStatus, AutoStep>> = {
  split: {
    next: "approval",
    delay: 2500,
    toast: { tone: "sun", text: "按分を計算しました。承認者に Slack で承認を依頼しています" },
    guestOnly: false,
  },
  rsvp: {
    next: "venue",
    delay: 4000,
    toast: { tone: "navy", label: "デモ用の代行", text: "参加者（架空）3名が出欠と委任に回答しました。帰りやすいお店を探しました" },
    guestOnly: true,
  },
  booked: {
    next: "day_of",
    delay: 3000,
    toast: { tone: "navy", label: "デモ用の早送り", text: "開催日まで早送りしました。出席を確認しています" },
    guestOnly: true,
  },
  day_of: {
    next: "receipt",
    delay: 3000,
    toast: { tone: "sun", label: "確認待ち", text: "開催が終わりました。領収書をアップロードしてください" },
    guestOnly: true,
  },
  approval: {
    next: "payment",
    delay: 4000,
    toast: { tone: "navy", label: "デモ用の代行", text: "承認者（架空）が Slack で按分を承認しました。振込を依頼しています" },
    guestOnly: true,
  },
  payment: {
    next: "completed",
    delay: 5000,
    toast: { tone: "lagoon", label: "デモ用の代行", text: "参加者（架空）が銀行で承認し、全員の入金を明細で確認しました" },
    guestOnly: true,
  },
  completed: {
    next: "retro",
    delay: 4000,
    toast: { tone: "sun", label: "確認待ち", text: "振り返り（架空）が 7名分集まりました。次回に覚えさせる内容を確認してください" },
    guestOnly: true,
  },
};

export function EventDetailView({ eventId }: { eventId: string }) {
  const role = useDemoRole();
  const stage = useDemoStage();
  const href = useDemoHref();
  const { data: event, loading, raw, reload } = useEventDetail(eventId, role, stage);

  if (loading) return <main className={styles.page} aria-busy="true" />;
  if (!event) {
    // 存在するかどうかが推測できる文言にしない（DESIGN.md「Empty / Loading / Error」）
    return (
      <main className={styles.page}>
        <Card>
          <EmptyState title="この画面を見る権限がありません">
            <TextLink href={href("/events")}>イベントの一覧へ</TextLink>
          </EmptyState>
        </Card>
      </main>
    );
  }

  // 役割が変わったら画面の中の状態を最初からにする。段階が変わっても KUROKO Panel は保つ（新着を知らせるため）
  return <EventDetailBody key={`${eventId}-${role}`} event={event} role={role} api={raw} reload={reload} />;
}

function EventDetailBody({
  event,
  role,
  api,
  reload,
}: {
  event: EventDetail;
  role: Role;
  api: ApiEventDetail | null;
  reload: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const href = useDemoHref();
  const { toast } = useToast();
  const tabBarRef = useRef<HTMLDivElement>(null);
  // 店を選んだ段階（別の段階へ移ったら、選び直しから）
  const [venueChosenAt, setVenueChosenAt] = useState<EventStatus | null>(null);
  const venueChosen = venueChosenAt === event.status;
  const [retroDecision, setRetroDecision] = useState<RetroDecision | null>(null);

  const isGuest = role === "guest";
  const tabParam = params.get("tab");
  const tab: DetailTab = TABS.includes(tabParam as DetailTab) ? (tabParam as DetailTab) : defaultTab(event.status);

  const replaceQuery = useCallback(
    (next: Record<string, string | null>) => {
      const search = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value === null) search.delete(key);
        else search.set(key, value);
      }
      router.replace(`${pathname}?${search.toString()}`, { scroll: false });
    },
    [params, pathname, router],
  );

  /** 段階を進める。トースト → Flow Stepper → タブの中身 の順にずらす（DESIGN.md「Motion」） */
  const advance = useCallback(
    (next: EventStatus, message: Omit<ToastInput, "eventId">, options?: { scrollTop?: boolean }) => {
      toast({ ...message, eventId: event.eventId });
      // 幹事が確定したときは、全体フローが進むところを見せるため上へ戻す
      if (options?.scrollTop) window.scrollTo({ top: 0, behavior: "smooth" });
      setTimeout(() => replaceQuery({ stage: next, tab: null }), STAGGER * 1000);
    },
    [event.eventId, replaceQuery, toast],
  );

  useEffect(() => {
    if (USE_API) return; // 実 API のときは、段階は実際の操作でだけ進む（ダミーの自動進行はしない）
    const step = AUTO[event.status];
    if (!step) return;
    if (step.guestOnly && !(isGuest && event.sandbox)) return;
    const timer = setTimeout(() => advance(step.next, step.toast), step.delay);
    return () => clearTimeout(timer);
  }, [event.status, event.sandbox, isGuest, advance]);

  const jumpToTab = (next: DetailTab) => {
    replaceQuery({ tab: next });
    tabBarRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const waitingCount = event.participants.filter((p) => CONSENT_STATE[p.consent].tone === "sun").length;
  const retroWaiting = event.retrospective?.status === "awaiting_organizer" && !retroDecision;
  const tabs: TabItem<DetailTab>[] = [
    {
      value: "payments",
      label: "送金・承諾",
      meta: event.consentTargetCount > 0 ? `${event.consentedCount}/${event.consentTargetCount}` : undefined,
      dot: waitingCount > 0 ? "sun" : undefined,
    },
    { value: "split", label: "按分", dot: event.split?.approval.status === "pending" ? "sun" : undefined },
    { value: "retro", label: "振り返り", dot: retroWaiting ? "sun" : undefined },
    { value: "log", label: "経緯", meta: String(event.decisionLog.length) },
  ];

  return (
    <main className={styles.page}>
      <div>
        <TextLink href={href("/events")}>← イベントの一覧</TextLink>
      </div>

      <EventSummary event={event} onJump={() => jumpToTab("payments")} />

      {USE_API && api && (
        <>
          <ScenarioHint hint={api.hint} />
          {/* 幹事の入力は、チャットの画面（KUROKO との DM）で行う。ここは状況を見る画面（SPEC 7.5） */}
          <InfoBanner action={<TextLink href={api.ui_mode === "live" ? "/demo" : "/verify"}>チャットを開く</TextLink>}>
            計画の確定・お店の選択・予約の画面や領収書の送信・振り返りの確認は、KUROKO とのチャットの中で行います。
          </InfoBanner>
        </>
      )}

      {/* 幹事の確認は、その段階のときだけ Event Summary の直下に出す（カードの中にカードを入れない） */}
      <AnimatePresence mode="popLayout" initial={false}>
        {event.status === "venue" && event.venueCandidates.length > 0 && (
          <motion.div key="venue" {...ENTER}>
            <VenueChoiceCard
              candidates={event.venueCandidates}
              onSelected={(c) => {
                setVenueChosenAt(event.status);
                toast({ tone: "navy", label: "選択", text: `「${c.name}」で進めます。予約したら、予約画面をアップロードしてください` });
              }}
            />
          </motion.div>
        )}
        {event.status === "venue" && venueChosen && event.reservation && (
          <motion.div key="reservation" {...ENTER}>
            <ConfirmationCard
              extraction={event.reservation}
              isGuest={isGuest}
              onConfirmed={(source) =>
                advance(
                  "booked",
                  { tone: "lagoon", text: `予約内容を${sourceLabel(source)}確定しました。コース単価は規程の上限以内です` },
                  { scrollTop: true },
                )
              }
            />
          </motion.div>
        )}
        {event.status === "receipt" && event.receipt && (
          <motion.div key="receipt" {...ENTER}>
            <ConfirmationCard
              extraction={event.receipt}
              isGuest={isGuest}
              onConfirmed={(source) =>
                advance(
                  "split",
                  { tone: "lagoon", text: `領収書の金額を${sourceLabel(source)}確定しました。按分を計算します` },
                  { scrollTop: true },
                )
              }
            />
          </motion.div>
        )}
      </AnimatePresence>

      <div ref={tabBarRef} className={detail.tabBar}>
        <Tabs items={tabs} value={tab} onChange={(t) => replaceQuery({ tab: t })} label="イベントの詳細" idPrefix="detail" />
      </div>

      <div role="tabpanel" id="detail-panel" aria-labelledby={`detail-tab-${tab}`}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={tab}
            className={detail.tabPanel}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={FADE_UP}
          >
            {tab === "payments" && (
              <div className={styles.twoCol}>
                <PaymentTable payments={event.payments} participants={event.participants} />
                <ConsentList participants={event.participants} />
              </div>
            )}
            {tab === "split" &&
              (event.split ? (
                <SplitTable split={event.split} participants={event.participants} />
              ) : (
                <Card>
                  <EmptyState title="まだ按分していません">
                    開催後に領収書の金額を確定すると、規程に沿って按分し、誰がいくら払うかがここに出ます。
                  </EmptyState>
                </Card>
              ))}
            {tab === "retro" &&
              (event.retrospective ? (
                <RetroSummaryCard
                  retro={event.retrospective}
                  decided={retroDecision}
                  onDecide={(d) => {
                    setRetroDecision(d);
                    advance(
                      "closed",
                      d.decision === "saved"
                        ? { tone: "lagoon", text: `次回に覚えさせる内容を ${d.includedIds.length}件 保存しました` }
                        : { tone: "slate", text: "今回の振り返りは、記憶に保存しませんでした" },
                      { scrollTop: true },
                    );
                  }}
                />
              ) : (
                <Card>
                  <EmptyState title="振り返りはまだです">
                    送金が完了した翌日に、参加者へ振り返りをお願いします。集まると、ここに集計と覚えさせる内容が出ます。
                  </EmptyState>
                </Card>
              ))}
            {tab === "log" && <DecisionTimeline entries={event.decisionLog} />}
          </motion.div>
        </AnimatePresence>
      </div>

      {USE_API ? (
        <ApiChatCard eventId={event.eventId} messages={event.messages} onSent={reload} />
      ) : (
      <KurokoDock
        messages={event.messages}
        activity={event.activity}
        defaultOpen={event.status === "planning"}
        onConfirmPlan={() =>
          advance("rsvp", { tone: "lagoon", text: "イベントの計画を確定しました。Slack で参加者に出欠の依頼を送りました" })
        }
      />
      )}
    </main>
  );
}

/** トーストの文に入れる入力元（手入力のときだけ書く） */
function sourceLabel(source: InputSource): string {
  return source === "manual" ? "手入力で" : "";
}

const ENTER = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12, transition: { duration: 0.2 } },
  transition: FADE_UP,
  layout: true,
} as const;
