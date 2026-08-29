import { useEffect, useState, type RefObject } from "react";
import { apiGet } from "../api/client";
import { liveLapsSchema, liveTelemetrySchema, type LapsResponse } from "../api/types";

function replayQuery(replayKey?: number | null, asOf?: string | null) {
  if (replayKey == null) return "";
  const asOfPart = asOf ? `&as_of=${encodeURIComponent(asOf)}` : "";
  return `?replay_session_key=${replayKey}${asOfPart}`;
}

export function useLiveLaps(
  active: boolean,
  replayKey?: number | null,
  asOfRef?: RefObject<string | null>,
) {
  const [data, setData] = useState<LapsResponse | undefined>();
  const [error, setError] = useState<string | undefined>();
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const path = `/api/live/laps${replayQuery(replayKey, asOfRef?.current ?? null)}`;
        const raw = await apiGet(path, {
          schema: liveLapsSchema,
          timeout: 20_000,
          cache: false,
        });
        if (cancelled) return;
        setData({
          year: 2026,
          round_number: 0,
          session_type: replayKey != null ? "REPLAY" : "LIVE",
          laps: raw.laps,
        });
        setStatus("ok");
        setError(undefined);
      } catch (err) {
        if (!cancelled) {
          setStatus("error");
          setError(err instanceof Error ? err.message : String(err));
        }
      }
    };
    void poll();
    const id = window.setInterval(() => void poll(), replayKey != null ? 2000 : 2_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [active, replayKey, asOfRef]);
  return { status, data, error, retry: () => undefined };
}

export function useLiveTelemetry(
  driver: string,
  active: boolean,
  replayKey?: number | null,
  asOfRef?: RefObject<string | null>,
) {
  const [tel, setTel] = useState<{
    distance: number[];
    speed: number[];
    throttle: number[];
    brake: number[];
  } | null>(null);
  useEffect(() => {
    if (!active || !driver) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const path = `/api/live/telemetry?driver=${encodeURIComponent(driver)}${
          replayKey != null
            ? `&replay_session_key=${replayKey}${
                asOfRef?.current ? `&as_of=${encodeURIComponent(asOfRef.current)}` : ""
              }`
            : ""
        }`;
        const raw = await apiGet(path, {
          schema: liveTelemetrySchema,
          timeout: 12_000,
          cache: false,
        });
        if (cancelled) return;
        setTel({
          distance: raw.t_s,
          speed: raw.speed,
          throttle: raw.throttle,
          brake: raw.brake,
        });
      } catch {
        if (!cancelled) setTel(null);
      }
    };
    void poll();
    const id = window.setInterval(() => void poll(), 800);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [driver, active, replayKey, asOfRef]);
  return tel;
}
