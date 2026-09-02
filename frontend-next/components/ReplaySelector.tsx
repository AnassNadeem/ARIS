"use client";

import { REPLAY_YEAR_BLOCKED_MSG, REPLAY_YEAR_TOOLTIP, replayYears } from "@/lib/replayFilter";
import { circuitBadge } from "@/lib/sessionFlow";
import type { RoundCard } from "@/lib/types";

const YEARS = replayYears();

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function ReplaySelector({
  year,
  rounds,
  selected,
  selectedSession,
  loading,
  yearBlocked,
  arisEnabled,
  onYearChange,
  onSelect,
  onContinue,
  onArisChange,
}: {
  year: number;
  rounds: RoundCard[];
  selected: RoundCard | null;
  selectedSession?: string | null;
  loading?: boolean;
  yearBlocked?: boolean;
  arisEnabled: boolean;
  onYearChange: (year: number) => void;
  onSelect: (round: RoundCard) => void;
  onContinue: () => void;
  onArisChange: (on: boolean) => void;
}) {
  return (
    <section className="flex flex-col gap-5">
      {yearBlocked && (
        <p
          role="alert"
          className="rounded-[8px] border border-safety/40 bg-safety/10 px-3 py-2 font-mono-data text-[11px] text-safety"
        >
          {REPLAY_YEAR_BLOCKED_MSG}
        </p>
      )}

      <div>
        <div className="font-mono-data text-[10px] uppercase tracking-[0.22em] text-red">ARIS</div>
        <h2 className="mt-1 text-xl font-bold tracking-wide text-white uppercase sm:text-2xl">Replay with ARIS</h2>
        <p className="mt-1 font-mono-data text-[11px] text-muted">
          Toggle ARIS first, then pick a season and race. Cancelled, upcoming, and future-dated weekends are hidden.
        </p>
        <div className="mt-3 inline-flex w-fit overflow-hidden rounded-[8px] border border-border bg-obsidian" role="group" aria-label="ARIS toggle">
          <button
            type="button"
            aria-pressed={!arisEnabled}
            onClick={() => onArisChange(false)}
            className={`px-5 py-2.5 font-mono-data text-[12px] uppercase tracking-widest ${
              !arisEnabled ? "bg-red/15 text-red" : "text-muted hover:text-white"
            }`}
          >
            Off
          </button>
          <button
            type="button"
            aria-pressed={arisEnabled}
            onClick={() => onArisChange(true)}
            className={`px-5 py-2.5 font-mono-data text-[12px] uppercase tracking-widest ${
              arisEnabled ? "bg-safety/20 text-safety" : "text-muted hover:text-white"
            }`}
          >
            On
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="font-mono-data text-[10px] uppercase tracking-[0.22em] text-red">Season & race</div>
          <p className="mt-1 font-mono-data text-[11px] text-muted">Scroll the list — the first completed race is selected.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono-data text-[10px] uppercase tracking-widest text-muted">Season</span>
          <div className="flex overflow-visible rounded-[8px] border border-border bg-obsidian" role="group" aria-label="Replay season">
            {YEARS.slice()
              .reverse()
              .map((y) => {
                const on = year === y;
                return (
                  <button
                    key={y}
                    type="button"
                    title={REPLAY_YEAR_TOOLTIP}
                    aria-pressed={on}
                    aria-label={`${y}. ${REPLAY_YEAR_TOOLTIP}`}
                    onClick={() => onYearChange(y)}
                    className={`group relative px-3.5 py-1.5 font-mono-data text-sm outline-none transition-colors first:rounded-l-[7px] last:rounded-r-[7px] focus-visible:ring-1 focus-visible:ring-red ${
                      on ? "bg-red/15 text-red" : "text-muted hover:bg-surface hover:text-white"
                    }`}
                  >
                    {y}
                    <span className="pointer-events-none absolute bottom-[calc(100%+8px)] left-1/2 z-20 w-max max-w-[220px] -translate-x-1/2 rounded border border-border bg-obsidian px-2 py-1 text-center font-mono-data text-[10px] leading-snug text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                      {REPLAY_YEAR_TOOLTIP}
                    </span>
                  </button>
                );
              })}
          </div>
        </div>
      </div>

      {loading && rounds.length === 0 && (
        <div className="h-[88px] animate-pulse rounded-[8px] border border-border bg-obsidian" />
      )}

      {!loading && rounds.length === 0 && (
        <p className="font-mono-data text-[11px] text-muted">
          No completed races for {year} yet (cancelled and upcoming rounds are hidden).
        </p>
      )}

      <div className="flex gap-2 overflow-x-auto pb-2 [scrollbar-width:thin]">
        {rounds.map((r) => {
          const on = selected?.round === r.round;
          const live = r.status === "LIVE";
          return (
            <button
              key={r.round}
              type="button"
              onClick={() => onSelect(r)}
              className={`replay-panel w-[168px] shrink-0 rounded-[8px] border p-2.5 text-left transition-colors ${
                on ? "border-red replay-glow-red" : "border-border hover:border-red/40"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xl leading-none" aria-hidden>
                  {r.countryFlag}
                </span>
                <span className="font-mono-data text-[10px] text-muted">R{r.round}</span>
              </div>
              <div className="mt-1.5 truncate font-mono-data text-[12px] font-semibold text-white">{r.circuitName}</div>
              <div className="mt-0.5 font-mono-data text-[10px] text-muted">{formatDate(r.date)}</div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {live && (
                  <span className="rounded bg-safety/20 px-1.5 py-0.5 font-mono-data text-[9px] uppercase tracking-wide text-safety">
                    Live
                  </span>
                )}
                <span
                  className={`rounded px-1.5 py-0.5 font-mono-data text-[9px] uppercase tracking-wide ${
                    on ? "bg-red/15 text-red" : "bg-obsidian text-muted"
                  }`}
                >
                  {circuitBadge(r, on ? selectedSession : null)}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {selected && (
        <button
          type="button"
          onClick={onContinue}
          className="self-start rounded-[8px] border border-red bg-red/10 px-5 py-2.5 font-mono-data text-[11px] uppercase tracking-widest text-red hover:bg-red/20"
        >
          {arisEnabled ? `Continue with ${selected.circuitName} →` : `Start Race · ${selected.circuitName} →`}
        </button>
      )}
    </section>
  );
}
