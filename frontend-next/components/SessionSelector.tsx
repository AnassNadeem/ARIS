"use client";

import {
  SESSION_OPTIONS,
  isArisCapableSession,
  sessionAvailability,
  type SessionOption,
} from "@/lib/sessionFlow";
import type { RoundCard } from "@/lib/types";

export function SessionSelector({
  round,
  selectedId,
  sessionStatus,
  onSelect,
}: {
  round: RoundCard;
  selectedId: string;
  sessionStatus: Record<string, string>;
  onSelect: (option: SessionOption) => void;
}) {
  return (
    <div>
      <div className="font-mono-data text-[10px] uppercase tracking-[0.22em] text-red">Select session</div>
      <p className="mt-1 font-mono-data text-[11px] text-muted">
        {round.countryFlag} {round.circuitName}
        {round.isSprint ? " · sprint weekend" : " · standard weekend"}
      </p>
      <div className="mt-3 grid grid-cols-4 gap-2 sm:grid-cols-8">
        {SESSION_OPTIONS.map((opt) => {
          const avail = sessionAvailability(opt, round.isSprint, sessionStatus);
          const selected = selectedId === opt.id;
          const aris = isArisCapableSession(opt.type);
          return (
            <button
              key={opt.id}
              type="button"
              disabled={!avail.enabled}
              title={
                !avail.enabled
                  ? avail.reason
                  : aris
                    ? "Competitive session — ARIS strategy is available."
                    : "Replayable — ARIS is restricted to Race and Sprint."
              }
              onClick={() => onSelect(opt)}
              className={`rounded-[8px] border px-2 py-2.5 font-mono-data text-[11px] uppercase tracking-wide transition-colors ${
                !avail.enabled
                  ? "cursor-not-allowed border-border bg-obsidian text-muted-2 opacity-40"
                  : selected
                    ? aris
                      ? "border-safety bg-safety/15 text-white replay-glow-red"
                      : "border-red bg-red/10 text-white replay-glow-red"
                    : "border-border bg-obsidian text-muted hover:border-red/50 hover:text-white"
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
