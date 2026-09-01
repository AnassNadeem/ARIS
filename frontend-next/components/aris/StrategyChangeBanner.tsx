"use client";

import { useEffect, useState } from "react";
import { useRaceStore } from "@/store/raceStore";

const AUTO_DISMISS_MS = 9000;

const KIND_LABEL: Record<string, string> = {
  strategy_change: "STRATEGY CHANGE",
  sc_window: "SC PIT WINDOW",
  red_flag_reset: "RED FLAG RESTART",
  wet_switch: "WEATHER TYRE CALL",
  pit_now: "BOXING NOW",
};

/**
 * A big, unmissable box for material ARIS decisions — strategy changes and
 * pit calls. Auto mode never asks the user before acting on these; this
 * banner is how it "tells" instead: large, high-contrast, briefly pinned
 * above the console rather than buried in the scrolling comms feed.
 */
export function StrategyChangeBanner() {
  const decision = useRaceStore((s) => s.bigDecision);
  const clear = useRaceStore((s) => s.setBigDecision);
  const [dismissed, setDismissed] = useState<string | null>(null);

  useEffect(() => {
    if (!decision) return;
    const t = setTimeout(() => clear(null), AUTO_DISMISS_MS);
    return () => clearTimeout(t);
  }, [decision, clear]);

  if (!decision || dismissed === decision.id) return null;

  const label = KIND_LABEL[decision.kind ?? "strategy_change"] ?? "ARIS DECISION";

  return (
    <div
      role="alert"
      data-testid="strategy-change-banner"
      className="relative z-30 mx-3 mt-2 shrink-0 animate-[fadeInBanner_0.2s_ease-out] rounded-lg border-2 border-red bg-gradient-to-r from-red/25 via-surface to-surface px-4 py-3 shadow-[0_0_24px_rgba(232,0,45,0.35)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-red font-mono-data text-[13px] font-bold text-red">
            !
          </span>
          <div>
            <div className="font-mono-data text-[13px] font-bold uppercase tracking-wide text-white">
              L{decision.lap} — {label}
            </div>
            <div className="mt-0.5 max-w-2xl font-sans text-[13px] leading-snug text-white/90">{decision.text}</div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            setDismissed(decision.id);
            clear(null);
          }}
          className="shrink-0 rounded border border-white/30 px-2 py-0.5 font-mono-data text-[10px] uppercase text-white/70 hover:border-white hover:text-white"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
