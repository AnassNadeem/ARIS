"use client";

import { useCountdown } from "@/lib/useCountdown";
import { hubSessionCta } from "@/lib/liveSetup";
import { isArisCapableSession, sessionLabel } from "@/lib/sessionFlow";
import { sessionIsLiveNow } from "@/lib/sessionWindow";
import type { HubSession, LiveHub } from "@/lib/types";

function UpcomingCountdown({ iso }: { iso: string }) {
  const countdown = useCountdown(iso);
  return <span className="font-mono-data text-[12px] text-red">{countdown}</span>;
}

function SessionTimer({ session }: { session: HubSession }) {
  const live = sessionIsLiveNow(session);
  const upcoming =
    !live &&
    session.status === "UPCOMING" &&
    Boolean(session.datetime_utc) &&
    new Date(session.datetime_utc!).getTime() > Date.now();

  if (live) {
    return (
      <span className="flex items-center gap-1.5 font-mono-data text-[12px] text-red">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red" />
        LIVE
      </span>
    );
  }
  if (session.status === "COMPLETED" || session.replayable) {
    return <span className="font-mono-data text-[12px] text-muted">Replay</span>;
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

function ctaLabel(session: HubSession): string {
  const name = sessionLabel(session.session_type);
  const cta = hubSessionCta(session);
  if (cta === "live") return `Go Live · ${name} →`;
  if (cta === "replay") return `Replay ${name} →`;
  return `Open console · ${name} →`;
}

export function LiveSessionPicker({
  hub,
  selected,
  arisEnabled,
  onSelect,
  onContinue,
  onArisChange,
}: {
  hub: LiveHub;
  selected: HubSession | null;
  arisEnabled: boolean;
  onSelect: (session: HubSession) => void;
  onContinue: () => void;
  onArisChange: (on: boolean) => void;
}) {
  const dateLabel = hub.next.date_race
    ? new Date(hub.next.date_race).toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
      })
    : "";
  const arisBlocked = Boolean(selected && !isArisCapableSession(selected.session_type) && arisEnabled);

  return (
    <section className="flex flex-col gap-5">
      <div>
        <div className="font-mono-data text-[10px] uppercase tracking-[0.22em] text-red">ARIS</div>
        <h2 className="mt-1 text-xl font-bold tracking-wide text-white uppercase sm:text-2xl">Live timing</h2>
        <p className="mt-1 font-mono-data text-[11px] text-muted">
          Pick this weekend&apos;s session. Completed sessions open as replay. Live sessions open the pit wall at the
          current lap.
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
              arisEnabled ? "bg-red/15 text-red" : "text-muted hover:text-white"
            }`}
          >
            On
          </button>
        </div>
        <p className="mt-2 font-mono-data text-[11px] text-muted">
          {arisEnabled
            ? selected && !isArisCapableSession(selected.session_type)
              ? "ARIS on is Race and FP2 — pick one of those sessions."
              : "ARIS on — ghost car and delta will show on the timing tower."
            : "ARIS off — timing only."}
        </p>
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
          const live = sessionIsLiveNow(s);
          const replay = s.status === "COMPLETED" || s.replayable;
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
                {live ? (
                  <span className="rounded bg-red/20 px-1.5 py-0.5 font-mono-data text-[9px] uppercase tracking-wide text-red">
                    Live
                  </span>
                ) : replay ? (
                  <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono-data text-[9px] uppercase tracking-wide text-white">
                    Replay
                  </span>
                ) : null}
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
          disabled={arisBlocked}
          className={`self-start rounded-[8px] border px-5 py-2.5 font-mono-data text-[11px] uppercase tracking-widest ${
            arisBlocked
              ? "cursor-not-allowed border-border text-muted-2"
              : "border-red bg-red/10 text-red hover:bg-red/20"
          }`}
        >
          {ctaLabel(selected)}
        </button>
      )}
    </section>
  );
}
