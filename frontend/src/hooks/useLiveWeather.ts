import { useEffect, useState } from "react";
import { apiGet, asOfFromUrl, withAsOf } from "../api/client";
import type { LiveWeather } from "../api/types";
import { liveWeatherSchema } from "../api/types";

export function useLiveWeather(active: boolean, replaySessionKey?: number | null) {
  const [weather, setWeather] = useState<LiveWeather | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const asOf = asOfFromUrl();
    const poll = async () => {
      try {
        const extra = replaySessionKey != null ? `?replay_session_key=${replaySessionKey}` : "";
        const data = await apiGet(withAsOf(`/api/live/weather${extra}`, asOf), {
          schema: liveWeatherSchema,
          timeout: 20_000,
          cache: false,
        });
        if (!cancelled) {
          setWeather(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    };
    void poll();
    const id = window.setInterval(() => void poll(), 8_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [active, replaySessionKey]);
  return { weather, error };
}
