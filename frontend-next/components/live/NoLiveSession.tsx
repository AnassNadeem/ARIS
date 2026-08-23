"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getNextRace } from "@/lib/api";
import { useCountdown } from "@/lib/useCountdown";
import type { NextRaceInfo } from "@/lib/types";

export function NoLiveSession({ onEnterDemo }: { onEnterDemo: () => void }) {
  const [info, setInfo] = useState<NextRaceInfo | null>(null);

  useEffect(() => {
    getNextRace().then(setInfo);
  }, []);

  const countdown = useCountdown(info?.countdownTargetIso ?? new Date().toISOString());

  if (!info) {
    return <div className="flex-1 p-10 font-mono-data text-sm text-muted">Loading race weekend…</div>;
  }

  return (
    <main className="flex-1 bg-carbon px-6 py-10">
      <div className="mx-auto flex max-w-5xl flex-col gap-10">
        {/* Hero */}
        <section className="rounded-[8px] border border-border bg-surface p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <div>
              <div className="font-mono-data text-xs uppercase tracking-widest text-muted">Next race</div>
              <h1 className="mt-1 text-3xl font-bold text-white">
                {info.countryFlag} {info.raceName}
              </h1>
              <div className="mt-1 font-mono-data text-sm text-muted">
                {info.circuitName} · {new Date(info.date).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
              </div>
            </div>
            <div className="text-right">
              <div className="font-mono-data text-xs uppercase text-muted">Countdown</div>
              <div className="font-mono-data text-2xl text-red">{countdown}</div>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            {info.sessions.map((s) => (
              <div key={s.name} className="rounded border border-border bg-carbon px-3 py-2">
                <div className="font-mono-data text-[10px] uppercase text-muted">{s.name}</div>
                <div className="font-mono-data text-sm text-white">{s.localTime}</div>
              </div>
            ))}
          </div>
          <button
            onClick={onEnterDemo}
            className="mt-6 rounded-[8px] bg-red px-5 py-2.5 font-mono-data text-xs uppercase text-white hover:brightness-110"
          >
            → Enter live session (demo)
          </button>
        </section>

        {/* Circuit info + strategy */}
        <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="rounded-[8px] border border-border bg-surface p-5">
            <h2 className="mb-3 font-mono-data text-xs uppercase text-muted">Circuit info</h2>
            <div className="font-mono-data text-sm text-white">{info.circuitName}</div>
            <div className="mt-2 grid grid-cols-2 gap-2 font-mono-data text-[12px] text-muted">
              <span>Length</span>
              <span className="text-right text-white">{info.circuitLengthKm.toFixed(3)} km</span>
              <span>Laps</span>
              <span className="text-right text-white">{info.numLaps}</span>
              <span>Lap record</span>
              <span className="text-right text-white">
                {info.lapRecord.time} ({info.lapRecord.driver}, {info.lapRecord.year})
              </span>
            </div>
          </div>

          <div className="rounded-[8px] border border-border bg-surface p-5">
            <h2 className="mb-1 font-mono-data text-xs uppercase text-muted">Possible tyre strategies</h2>
            <p className="mb-3 font-mono-data text-[10px] text-muted-2">
              Historical strategy patterns — not live ARIS recommendations.
            </p>
            <div className="flex flex-col gap-2">
              {info.strategyPatterns.map((p) => (
                <div key={p.label} className="rounded border border-border bg-carbon p-2.5">
                  <div className="font-mono-data text-[12px] text-white">{p.label}</div>
                  <div className="font-mono-data text-[10px] text-muted">— {p.note}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Race history */}
        <section className="rounded-[8px] border border-border bg-surface p-5">
          <h2 className="mb-3 font-mono-data text-xs uppercase text-muted">Recent race history</h2>
          <table className="w-full border-collapse font-mono-data text-[12px]">
            <thead>
              <tr className="border-b border-border text-left text-[10px] uppercase text-muted">
                <th className="py-1.5">Year</th>
                <th>Winner</th>
                <th>Pole</th>
                <th>Fastest lap</th>
                <th>Time</th>
                <th className="text-right">Race record</th>
              </tr>
            </thead>
            <tbody>
              {info.raceHistory.map((r) => (
                <tr key={r.year} className="border-b border-border/60">
                  <td className="py-1.5 text-white">{r.year}</td>
                  <td className="text-white">{r.winner}</td>
                  <td className="text-muted">{r.pole}</td>
                  <td className="text-muted">{r.fastestLapDriver}</td>
                  <td className="text-muted">{r.fastestLapTime}</td>
                  <td className="text-right text-muted">{r.raceRecord}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* Prior session replay */}
        {info.priorSessionReplay && (
          <section className="rounded-[8px] border border-border bg-surface p-5">
            <h3 className="font-mono-data text-sm text-white">{info.priorSessionReplay.sessionName}</h3>
            <div className="mt-1 font-mono-data text-[11px] text-muted">
              {info.priorSessionReplay.dateLabel} · {info.priorSessionReplay.circuitName}
            </div>
            <div className="mt-1 font-mono-data text-[11px] text-muted">
              P1: {info.priorSessionReplay.poleDriver} {info.priorSessionReplay.poleTime}
            </div>
            <Link
              href={`/replay?session=quali&year=${info.priorSessionReplay.year}&round=${info.priorSessionReplay.round}`}
              className="mt-3 inline-block rounded border border-border px-4 py-2 font-mono-data text-[11px] uppercase text-white hover:border-white"
            >
              Replay with analytics →
            </Link>
          </section>
        )}
      </div>
    </main>
  );
}
