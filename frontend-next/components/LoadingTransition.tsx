"use client";

import { useEffect, useRef } from "react";
import { useRaceStore } from "@/store/raceStore";
import { R2_RACE_UNAVAILABLE } from "@/lib/r2Replay";

function statusCopy(stage: string, ready: boolean, error: string | null): { title: string; detail: string } {
  if (error === R2_RACE_UNAVAILABLE) {
    return { title: error, detail: "This session has not been published yet. Try another race, or check back later." };
  }
  if (error) {
    return { title: error, detail: "The replay files could not be fetched. Check NEXT_PUBLIC_R2_BASE_URL and retry." };
  }
  if (ready || stage === "minimal" || stage === "full") {
    return { title: "Race data ready", detail: "You can start as soon as the console opens." };
  }
  if (stage === "metadata") {
    return { title: "Loading session metadata…", detail: "Circuit, session type, and race distance." };
  }
  return {
    title: "Preparing race data (laps, map)…",
    detail: "FastF1 laps and circuit outline. Full GPS continues in the background.",
  };
}

export function LoadingTransition({
  ready,
  circuitName,
  sessionLabel,
  error,
  onRetry,
  onComplete,
}: {
  ready: boolean;
  circuitName: string;
  sessionLabel: string;
  error?: string | null;
  onRetry?: () => void;
  onComplete: () => void;
}) {
  const packStage = useRaceStore((s) => s.packStage);
  const packProgress = useRaceStore((s) => s.packProgress);
  const finished = useRef(false);
  const copy = statusCopy(packStage, ready, error ?? null);
  const pct = error
    ? 0
    : ready
      ? 100
      : Math.max(8, Math.min(92, Math.round((packProgress || (packStage === "metadata" ? 0.15 : 0.35)) * 100)));

  useEffect(() => {
    if (!ready || error) {
      finished.current = false;
      return;
    }
    if (finished.current) return;
    finished.current = true;
    const t = window.setTimeout(onComplete, 420);
    return () => window.clearTimeout(t);
  }, [ready, error, onComplete]);

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-obsidian/85 px-4 backdrop-blur-sm">
      <div className="replay-panel w-full max-w-lg rounded-[8px] border border-red/30 p-6 replay-glow-red">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono-data text-sm font-bold uppercase tracking-[0.2em] text-white">
            <span className={`h-2 w-2 rounded-full ${error ? "bg-red" : "animate-pulse bg-safety"}`} />
            ARIS
          </div>
          <span className="font-mono-data text-2xl tabular-nums text-red">{error ? "—" : `${pct}%`}</span>
        </div>
        <p className="mt-2 font-mono-data text-[11px] uppercase tracking-widest text-muted">
          {circuitName} · {sessionLabel}
        </p>

        <div className="mt-4 h-2 overflow-hidden rounded-full bg-obsidian">
          <div
            className="replay-bar-fill h-full bg-red transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>

        <ul className="mt-4 flex flex-col gap-1 font-mono-data text-[11px]">
          <li className={packStage !== "empty" || ready ? "text-red" : "text-muted"}>
            <span className="mr-2">{packStage !== "empty" || ready ? "✓" : "·"}</span>
            Loading session metadata…
          </li>
          <li className={packStage === "minimal" || packStage === "full" || ready ? "text-red" : "text-muted"}>
            <span className="mr-2">{packStage === "minimal" || packStage === "full" || ready ? "✓" : "·"}</span>
            Preparing race data (laps, map)…
          </li>
          <li className={packStage === "full" ? "text-red" : "text-muted"}>
            <span className="mr-2">{packStage === "full" ? "✓" : "·"}</span>
            Full GPS / weather (background)
          </li>
        </ul>

        <p className={`mt-4 font-sans text-sm ${error ? "text-red" : "text-white"}`}>{copy.title}</p>
        <p className="mt-1 font-mono-data text-[11px] text-muted">{copy.detail}</p>
        {error && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 rounded border border-red px-3 py-1.5 font-mono-data text-[11px] uppercase tracking-widest text-red hover:bg-red/15"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
