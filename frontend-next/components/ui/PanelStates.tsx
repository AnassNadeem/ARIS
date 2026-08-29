"use client";

import { useRaceStore } from "@/store/raceStore";

/** True while the live/replay feed has not delivered a first car frame. */
export function usePanelFeedLoading(): boolean {
  return useRaceStore((s) => {
    if (s.waitingForRace) return true;
    const noCars = Object.keys(s.cars).length === 0;
    if (noCars && (s.connectionStatus === "connecting" || s.connectionStatus === "reconnecting")) {
      return true;
    }
    return false;
  });
}

export function PanelSkeleton({
  variant = "rows",
  rows = 8,
}: {
  variant?: "rows" | "map";
  rows?: number;
}) {
  if (variant === "map") {
    return (
      <div className="flex h-full items-center justify-center p-4" aria-busy="true" aria-label="Loading">
        <div className="panel-skeleton-bar h-full min-h-16 w-full rounded" />
      </div>
    );
  }
  return (
    <div className="flex h-full flex-col gap-2 p-4" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="panel-skeleton-bar h-4 rounded"
          style={{ width: `${64 + ((i * 11) % 28)}%` }}
        />
      ))}
    </div>
  );
}

export function PanelEmpty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex h-full items-center justify-center bg-carbon px-4 py-4">
      <div className="max-w-sm text-center">
        <p className="font-sans text-sm text-white">{title}</p>
        <p className="mt-2 font-sans text-xs leading-relaxed text-muted">{detail}</p>
      </div>
    </div>
  );
}
