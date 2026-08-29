import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";

export type LiveRcMessage = {
  utc_time?: string | null;
  lap?: number | null;
  flag?: string | null;
  category?: string | null;
  message?: string | null;
};

function rcKey(m: LiveRcMessage) {
  return `${m.utc_time || ""}|${m.flag || ""}|${m.message || ""}`;
}

function isPenalty(m: LiveRcMessage) {
  const blob = `${m.flag || ""} ${m.category || ""} ${m.message || ""}`.toUpperCase();
  return /PENALTY|STEWARD|INVESTIGATION|TIME DELETED|BLACK AND WHITE|DRIVE THROUGH|STOP.?GO|\b5 SECOND|\b10 SECOND/.test(
    blob,
  );
}

function isNotable(m: LiveRcMessage) {
  const blob = `${m.flag || ""} ${m.category || ""} ${m.message || ""}`.toUpperCase();
  if (isPenalty(m)) return true;
  return (
    /YELLOW|RED|SC|VSC|SAFETY|CRASH|INCIDENT|STOPPED|STRANDED|COLLISION|DEBRIS|MEDICAL/.test(blob) &&
    !/GREEN FLAG|TRACK CLEAR|LIGHTS OUT|INFRINGEMENT/.test(blob)
  );
}

export function useLiveRaceControl(active: boolean) {
  const [messages, setMessages] = useState<LiveRcMessage[]>([]);
  const seenRef = useRef<Set<string>>(new Set());
  const primedRef = useRef(false);
  const [fresh, setFresh] = useState<LiveRcMessage[]>([]);
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await apiGet<{ messages?: LiveRcMessage[] }>("/api/live/race-control", {
          timeout: 12_000,
          cache: false,
        });
        if (cancelled) return;
        const rows = data.messages ?? [];
        setMessages(rows);
        if (!primedRef.current) {
          primedRef.current = true;
          for (const row of rows) seenRef.current.add(rcKey(row));
          const penalties = rows.filter(isPenalty).slice(-8);
          const notable = rows.filter((row) => isNotable(row) && !isPenalty(row)).slice(-4);
          const primed = [...notable, ...penalties];
          if (primed.length) setFresh(primed);
          return;
        }
        const next: LiveRcMessage[] = [];
        for (const row of rows) {
          const key = rcKey(row);
          if (!key.trim() || seenRef.current.has(key)) continue;
          seenRef.current.add(key);
          next.push(row);
        }
        if (next.length) setFresh(next);
      } catch {
        if (!cancelled) setFresh([]);
      }
    };
    void poll();
    const id = window.setInterval(() => void poll(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [active]);
  return { messages, fresh };
}
