"use client";

import { useRaceStore } from "@/store/raceStore";

export function ConnectionStatus() {
  const status = useRaceStore((s) => s.connectionStatus);
  const lagMs = useRaceStore((s) => s.connectionLagMs);

  if (status === "disconnected") return null;

  const map = {
    connecting: { dot: "text-amber", text: "CONNECTING…" },
    connected: { dot: "text-green", text: `CONNECTED  OpenF1 · ${lagMs}ms lag` },
    reconnecting: { dot: "text-amber animate-pulse", text: "RECONNECTING…" },
  } as const;
  const cfg = map[status];

  return (
    <div className="flex items-center gap-1.5 font-mono-data text-[10px] uppercase">
      <span className={cfg.dot}>●</span>
      <span className={status === "reconnecting" ? "text-amber" : "text-muted"}>{cfg.text}</span>
    </div>
  );
}
