"use client";

import { useCountdown } from "@/lib/useCountdown";
import { isArisCapableSession, sessionLabel } from "@/lib/sessionFlow";
import type { HubSession, LiveHub } from "@/lib/types";

function UpcomingCountdown({ iso }: { iso: string }) {
  const countdown = useCountdown(iso);
  return <span className="font-mono-data text-[12px] text-red">{countdown}</span>;
}

function SessionTimer({ session }: { session: HubSession }) {
  const upcoming =
    !session.live &&
    session.status === "UPCOMING" &&
    Boolean(session.datetime_utc) &&
    new Date(session.datetime_utc!).getTime() > Date.now();

  if (session.live) {
    return (
      <span className="flex items-center gap-1.5 font-mono-data text-[12px] text-red">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red" />
        LIVE
      </span>
    );
  }
  if (session.status === "COMPLETED" || session.replayable) {
    return <span className="font-mono-data text-[12px] text-muted">Completed</span>;
  }
  if (upcoming && session.datetime_utc) {
    return <UpcomingCountdown iso={session.datetime_utc} />;
  }
  return <span className="font-mono-data text-[12px] text-muted">{session.status}</span>;
}

function sessionClock(session: HubSession): string {
  if (!session.datetime_utc) return "";
  const d = new Date(session.datetime_utc);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function LiveSessionPicker({
  hub,
  selected,
  arisEnabled,
  onSelect,
  onContinue,
  onArisChange,
  onEnterDemo,
}: {
  hub: LiveHub;
  selected: HubSession | null;
  arisEnabled: boolean;
  onSelect: (session: HubSession) => void;
  onContinue: () => void;
  onArisChange: (on: boolean) => void;
  onEnterDemo: () => void;
}) {
  const dateLabel = hub.next.date_race
    ? new Date(hub.next.date_race).toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
      })
    : "";
  const selectedLabel = selected ? sessionLabel(selected.session_type) : "";
  const arisAllowed = isArisCapableSession(selected?.session_type);

  return (
    <section className="flex flex-col gap-5">
      <div>
        <div className="font-mono-data text-[10px] uppercase tracking-[0.22em] text-red">ARIS</div>
        <h2 className="mt-1 text-xl font-bold tracking-wide text-white uppercase sm:text-2xl">Live with ARIS</h2>
        <p className="mt-1 font-mono-data text-[11px] text-muted">
          ARIS is Race-only. Pick this weekend&apos;s session — the console starts when live data arrives.
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
            disabled={!arisAllowed}
            title={!arisAllowed ? "ARIS runs on Race sessions only." : undefined}
            onClick={() => arisAllowed && onArisChange(true)}
            className={`px-5 py-2.5 font-mono-data text-[12px] uppercase tracking-widest ${
              !arisAllowed
                ? "cursor-not-allowed text-muted-2 opacity-50"
                : arisEnabled
                  ? "bg-safety/20 text-safety"
                  : "text-muted hover:text-white"
            }`}
          >
            On
          </button>
        </div>
        {!arisAllowed && (
          <p className="mt-2 font-mono-data text-[11px] text-muted">Select Race to enable ARIS.</p>
        )}
      </div>

      <div>
        <div className="font-mono-data text-[10px] uppercase tracking-[0.22em] text-red">This weekend</div>
        <h2 className="mt-1 text-xl font-bold tracking-wide text-white uppercase sm:text-2xl">
          {hub.circuit.country_flag} {hub.next.name}
        </h2>
        <p className="mt-1 font-mono-data text-[11px] text-muted">
          {hub.circuit.circuit_name}
          {dateLabel ? ` · ${dateLabel}` : ""}
        </p>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-2 [scrollbar-width:thin]">
        {hub.weekend_sessions.map((s) => {
          const on = selected?.session_type === s.session_type;
          return (
            <button
              key={s.session_type}
              type="button"
              onClick={() => onSelect(s)}
              className={`replay-panel w-[168px] shrink-0 rounded-[8px] border p-2.5 text-left transition-colors ${
                on ? "border-red replay-glow-red" : "border-border hover:border-red/40"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono-data text-[12px] font-semibold text-white">
                  {sessionLabel(s.session_type)}
                </span>
                {s.live && (
                  <span className="rounded bg-red/20 px-1.5 py-0.5 font-mono-data text-[9px] uppercase tracking-wide text-red">
                    Live
                  </span>
                )}
              </div>
              <div className="mt-1.5 font-mono-data text-[10px] text-muted">{sessionClock(s) || s.session_name}</div>
              <div className="mt-1.5">
                <SessionTimer session={s} />
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
          {arisEnabled && arisAllowed ? `Continue with ${selectedLabel} →` : `Go Live · ${selectedLabel} →`}
        </button>
      )}

      <button
        type="button"
        onClick={onEnterDemo}
        className="self-start font-mono-data text-[10px] uppercase tracking-widest text-muted hover:text-white"
      >
        Enter demo console
      </button>
    </section>
  );
}
