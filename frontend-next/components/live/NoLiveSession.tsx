"use client";

import Link from "next/link";
import { useCountdown } from "@/lib/useCountdown";
import type { HubSession, LiveHub } from "@/lib/types";
import { ARISToggle } from "@/components/aris/ARISToggle";

export function NoLiveSession({
  hub,
  onEnterLive,
  onEnterReplay,
  onEnterDemo,
}: {
  hub: LiveHub | null;
  onEnterLive: (sess: HubSession) => void;
  onEnterReplay: (sess: HubSession) => void;
  onEnterDemo: () => void;
}) {
  const target = hub?.countdown_target ?? hub?.next.next_session_datetime ?? new Date().toISOString();
  const countdown = useCountdown(target);

  if (!hub) {
    return <div className="flex-1 p-10 font-mono-data text-sm text-muted">Loading race weekend…</div>;
  }

  const waitingRace = hub.mode === "waiting_for_session";
  const liveNow = hub.mode === "live_session";
  const title = liveNow ? "Live now" : waitingRace ? "This weekend" : "Next race";
  const dateLabel = hub.next.date_race
    ? new Date(hub.next.date_race).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })
    : "";

  return (
    <main className="flex-1 bg-carbon px-6 py-10">
      <div className="mx-auto flex max-w-5xl flex-col gap-10">
        <section className="rounded-[8px] border border-border bg-surface p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <div>
              <div className="font-mono-data text-xs uppercase tracking-widest text-muted">
                {liveNow ? (
                  <span className="flex items-center gap-1.5 text-red">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red" /> {title}
                  </span>
                ) : (
                  title
                )}
              </div>
              <h1 className="mt-1 text-3xl font-bold text-white">
                {hub.circuit.country_flag} {hub.next.name}
              </h1>
              <div className="mt-1 font-mono-data text-sm text-muted">
                {hub.circuit.circuit_name} · {dateLabel}
              </div>
            </div>
            <div className="text-right">
              <div className="font-mono-data text-xs uppercase text-muted">
                {liveNow ? "Session" : "Countdown"}
              </div>
              <div className="font-mono-data text-2xl text-red">
                {liveNow ? hub.live.session_name ?? "LIVE" : countdown}
              </div>
              {hub.next.next_session_name && !liveNow && (
                <div className="mt-1 font-mono-data text-[11px] text-muted">until {hub.next.next_session_name}</div>
              )}
            </div>
          </div>

          {waitingRace && hub.waiting_reason && (
            <div className="mt-4 rounded border border-amber/40 bg-amber/10 px-3 py-2 font-mono-data text-[12px] text-amber">
              {hub.waiting_reason}
            </div>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            {hub.weekend_sessions.map((s) => (
              <SessionChip key={s.session_type} session={s} onLive={onEnterLive} onReplay={onEnterReplay} />
            ))}
          </div>

          <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            {liveNow ? (
              <button
                onClick={() => {
                  const live = hub.weekend_sessions.find((s) => s.live);
                  if (live) onEnterLive(live);
                }}
                className="rounded-[8px] bg-red px-5 py-2.5 font-mono-data text-xs uppercase text-white hover:brightness-110"
              >
                ● Watch live →
              </button>
            ) : (
              <button
                onClick={onEnterDemo}
                className="rounded-[8px] border border-border px-5 py-2.5 font-mono-data text-xs uppercase text-muted hover:border-white hover:text-white"
              >
                Enter demo console
              </button>
            )}
            <div className="w-full max-w-xs">
              <div className="mb-2 font-mono-data text-[10px] uppercase text-muted">ARIS for this session</div>
              <ARISToggle />
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="rounded-[8px] border border-border bg-surface p-5">
            <h2 className="mb-3 font-mono-data text-xs uppercase text-muted">Circuit info</h2>
            <div className="font-mono-data text-sm text-white">{hub.circuit.circuit_name}</div>
            <div className="mt-2 grid grid-cols-2 gap-2 font-mono-data text-[12px] text-muted">
              <span>Length</span>
              <span className="text-right text-white">
                {hub.circuit.length_km != null ? `${hub.circuit.length_km.toFixed(3)} km` : "—"}
              </span>
              <span>Laps</span>
              <span className="text-right text-white">{hub.circuit.total_laps ?? "—"}</span>
              <span>Turns</span>
              <span className="text-right text-white">{hub.circuit.turns ?? "—"}</span>
              <span>Pit loss</span>
              <span className="text-right text-white">
                {hub.circuit.pit_loss_seconds != null ? `${hub.circuit.pit_loss_seconds.toFixed(1)}s` : "—"}
              </span>
              <span>Tyre stress</span>
              <span className="text-right text-white">{hub.circuit.tyre_stress_rating ?? "—"}</span>
            </div>
            {hub.circuit.notes[0] && (
              <p className="mt-3 font-mono-data text-[11px] text-muted-2">{hub.circuit.notes[0]}</p>
            )}
          </div>

          <div className="rounded-[8px] border border-border bg-surface p-5">
            <h2 className="mb-1 font-mono-data text-xs uppercase text-muted">Possible tyre strategies</h2>
            <p className="mb-3 font-mono-data text-[10px] text-muted-2">
              Historical strategy patterns — not live ARIS recommendations.
            </p>
            <div className="flex flex-col gap-2">
              {hub.circuit.strategy_patterns.map((p) => (
                <div key={p.label} className="rounded border border-border bg-carbon p-2.5">
                  <div className="font-mono-data text-[12px] text-white">{p.label}</div>
                  <div className="font-mono-data text-[10px] text-muted">— {p.note}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="rounded-[8px] border border-border bg-surface p-5">
          <h2 className="mb-3 font-mono-data text-xs uppercase text-muted">Recent race history</h2>
          <table className="w-full border-collapse font-mono-data text-[12px]">
            <thead>
              <tr className="border-b border-border text-left text-[10px] uppercase text-muted">
                <th className="py-1.5">Year</th>
                <th>Winner</th>
                <th>Pole</th>
                <th>Fastest lap</th>
              </tr>
            </thead>
            <tbody>
              {hub.circuit.race_history.map((r) => (
                <tr key={r.year} className="border-b border-border/60">
                  <td className="py-1.5 text-white">{r.year}</td>
                  <td className="text-white">{r.winner ?? "—"}</td>
                  <td className="text-muted">{r.pole ?? "—"}</td>
                  <td className="text-muted">{r.fastest_lap ?? "—"}</td>
                </tr>
              ))}
              {hub.circuit.race_history.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-3 text-muted">
                    History loads from Jolpica when the circuit cache is warm.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        {hub.weekend_sessions.some((s) => s.replayable) && (
          <section className="rounded-[8px] border border-border bg-surface p-5">
            <h3 className="font-mono-data text-sm text-white">Completed sessions this weekend</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {hub.weekend_sessions.filter((s) => s.replayable).map((s) => (
                <button
                  key={s.session_type}
                  onClick={() => onEnterReplay(s)}
                  className="rounded border border-border px-4 py-2 font-mono-data text-[11px] uppercase text-white hover:border-white"
                >
                  Replay {s.session_type} →
                </button>
              ))}
            </div>
            <Link
              href={`/replay?year=${hub.next.year}&round=${hub.next.round_number}`}
              className="mt-3 inline-block font-mono-data text-[11px] uppercase text-muted hover:text-white"
            >
              Open replay selector →
            </Link>
          </section>
        )}
      </div>
    </main>
  );
}

function SessionChip({
  session,
  onLive,
  onReplay,
}: {
  session: HubSession;
  onLive: (s: HubSession) => void;
  onReplay: (s: HubSession) => void;
}) {
  const clickable = session.live || session.replayable;
  return (
    <button
      disabled={!clickable}
      onClick={() => (session.live ? onLive(session) : onReplay(session))}
      className={`rounded border px-3 py-2 text-left ${
        session.live
          ? "border-red bg-red/10"
          : session.replayable
            ? "border-border bg-carbon hover:border-white"
            : "cursor-not-allowed border-border bg-carbon opacity-50"
      }`}
    >
      <div className="font-mono-data text-[10px] uppercase text-muted">
        {session.session_type}
        {session.live && <span className="ml-1 text-red">LIVE</span>}
        {session.replayable && !session.live && <span className="ml-1 text-white">REPLAY</span>}
      </div>
      <div className="font-mono-data text-sm text-white">
        {session.datetime_utc
          ? new Date(session.datetime_utc).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
          : session.status}
      </div>
    </button>
  );
}
