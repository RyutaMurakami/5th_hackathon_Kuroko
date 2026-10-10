"use client";

// 画面が使うデータの取り方（ダミー／実 API の切り替えはここだけ。画面のコードは変わらない。TASKS F3）。
import { useCallback, useEffect, useState } from "react";
import { toEventDetail, toEventSummary, toNotification } from "./api-mappers";
import { ApiError, getEvent, listEvents as apiListEvents, listNotifications as apiListNotifications } from "./api-client";
import type { ApiEventDetail } from "./api-types";
import { useAuth } from "./auth";
import { USE_API } from "./data-source";
import { getEventDetail, listEvents, listNotifications } from "./mock-data";
import type { AppNotification, EventDetail, EventStatus, EventSummary, Role } from "./types";

const POLL_MS = 5000;

export type Loaded<T> = { data: T | null; loading: boolean; notFound: boolean; error: boolean; reload: () => void };

function useApiResource<T>(load: () => Promise<T>, poll: boolean): Loaded<T> {
  const { user } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!USE_API || !user) return; // ダミーのときは API を呼ばない
    let alive = true;
    const run = () =>
      load().then(
        (v) => {
          if (!alive) return;
          setData(v);
          setNotFound(false);
          setError(false);
          setLoading(false);
        },
        (e) => {
          if (!alive) return;
          // 存在するかどうかが推測できないよう、見られないものは「権限がない」と同じ扱い
          setNotFound(e instanceof ApiError && (e.status === 404 || e.status === 403));
          setError(!(e instanceof ApiError && (e.status === 404 || e.status === 403)));
          setLoading(false);
        },
      );
    void run();
    const timer = poll ? setInterval(() => void run(), POLL_MS) : undefined;
    return () => {
      alive = false;
      if (timer) clearInterval(timer);
    };
  }, [user, load, poll, tick]);

  return { data, loading, notFound, error, reload: useCallback(() => setTick((t) => t + 1), []) };
}

export function useEventList(role: Role): Loaded<EventSummary[]> {
  const load = useCallback(async () => (await apiListEvents()).map(toEventSummary), []);
  const api = useApiResource(load, true);
  if (!USE_API) return { data: listEvents(role), loading: false, notFound: false, error: false, reload: () => undefined };
  return api;
}

export function useEventDetail(
  eventId: string,
  role: Role,
  stage?: EventStatus,
): Loaded<EventDetail> & { raw: ApiEventDetail | null } {
  const [raw, setRaw] = useState<ApiEventDetail | null>(null);
  const load = useCallback(async () => {
    const r = await getEvent(eventId);
    setRaw(r);
    return toEventDetail(r);
  }, [eventId]);
  const api = useApiResource(load, true);
  if (!USE_API) {
    const d = getEventDetail(eventId, role, stage);
    return { data: d, loading: false, notFound: d === null, error: false, reload: () => undefined, raw: null };
  }
  return { ...api, raw };
}

export function useNotificationList(role: Role): Loaded<AppNotification[]> {
  const load = useCallback(async () => (await apiListNotifications()).map(toNotification), []);
  const api = useApiResource(load, true);
  if (!USE_API) return { data: listNotifications(role), loading: false, notFound: false, error: false, reload: () => undefined };
  return api;
}
