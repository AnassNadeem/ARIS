import { useEffect, useRef, useState } from "react";
import { apiGet, replaySessionKeyFromUrl, withAsOf, asOfFromUrl, apiUrl } from "../api/client";
import { liveStatusSchema, liveTimingSchema, type LiveStatus, type LiveTiming } from "../api/types";

export function useLiveTiming(active: boolean) {
  const [timing, setTiming] = useState<LiveTiming | null>(null);
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"sse" | "poll">("sse");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    let pollTimer: number | undefined;
    const asOf = asOfFromUrl();
    const replay = replaySessionKeyFromUrl();
    const extra = replay != null ? `replay_session_key=${replay}` : "";
    const q = extra ? `?${extra}` : "";

    const poll = async () => {
      try {
        const statusPath = withAsOf(`/api/live/status${q}`, asOf);
        const timingPath = withAsOf(`/api/live/timing${q}`, asOf);
        const [st, tm] = await Promise.all([
          apiGet(statusPath, { schema: liveStatusSchema, timeout: 60_000, cache: false }),
          apiGet(timingPath, { schema: liveTimingSchema, timeout: 60_000, cache: false }),
        ]);
        if (cancelled) return;
        setStatus(st);
        setTiming(tm);
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    };

    const startPoll = () => {
      setMode("poll");
      void poll();
      pollTimer = window.setInterval(() => void poll(), 5_000);
    };

    if (asOf) {
      startPoll();
      return () => {
        cancelled = true;
        if (pollTimer) window.clearInterval(pollTimer);
      };
    }

    try {
      const es = new EventSource(apiUrl(`/api/live/stream${q}`));
      esRef.current = es;
      es.onmessage = (ev) => {
        try {
          const payload = JSON.parse(ev.data) as { status: LiveStatus; timing: LiveTiming };
          setStatus(payload.status);
          setTiming(payload.timing);
          setError(null);
        } catch (err) {
          console.error("SSE parse", err);
        }
      };
      es.onerror = () => {
        es.close();
        esRef.current = null;
        startPoll();
      };
    } catch {
      startPoll();
    }

    return () => {
      cancelled = true;
      esRef.current?.close();
      if (pollTimer) window.clearInterval(pollTimer);
    };
  }, [active]);

  return { timing, status, error, mode };
}
