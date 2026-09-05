"use client";

import { useRaceStore } from "@/store/raceStore";

export function ConnectionStatus() {
  const status = useRaceStore((s) => s.connectionStatus);
  const consoleMode = useRaceStore((s) => s.consoleMode);

  if (status === "disconnected") return null;

  const feed = consoleMode === "live" ? "OpenF1" : "Replay";
  const connectedText =
    consoleMode === "live" ? `CONNECTED · ${feed} · ~5-7s delay` : `CONNECTED · ${feed}`;

  const map = {
    connecting: { dot: "text-amber", text: "CONNECTING…" },
    connected: { dot: "text-green", text: connectedText },
    reconnecting: { dot: "text-amber animate-pulse", text: "RECONNECTING…" },
  } as const;
  const cfg = map[status] ?? map.connecting;

  return (
    <div
      className="flex shrink-0 items-center gap-1.5 font-mono-data text-[10px] uppercase"
      data-connection-status={status}
    >
      <span className={cfg.dot}>●</span>
      <span className={status === "reconnecting" ? "text-amber" : "text-muted"}>{cfg.text}</span>
    </div>
  );
}
