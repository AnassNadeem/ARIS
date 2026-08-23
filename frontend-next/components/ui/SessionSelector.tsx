"use client";

import { useEffect, useState } from "react";
import { getCalendar, getSession } from "@/lib/api";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import { useRaceStore } from "@/store/raceStore";
import { ARISToggle } from "@/components/aris/ARISToggle";
import type { RoundCard } from "@/lib/types";

const YEARS = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018];

type SessionPill = { type: string; label: string; eligible: boolean };

function sessionPillsFor(round: RoundCard): SessionPill[] {
  const base: SessionPill[] = round.isSprint
    ? [
        { type: "FP1", label: "FP1", eligible: false },
        { type: "SQ", label: "SQ", eligible: false },
        { type: "S", label: "SPR", eligible: true },
        { type: "Q", label: "Q", eligible: false },
        { type: "R", label: "R", eligible: true },
      ]
    : [
        { type: "FP1", label: "FP1", eligible: false },
        { type: "FP2", label: "FP2", eligible: false },
        { type: "FP3", label: "FP3", eligible: false },
        { type: "Q", label: "Q", eligible: false },
        { type: "R", label: "R", eligible: true },
      ];
  return base;
}

export function SessionSelector({ onLoaded }: { onLoaded: () => void }) {
  const setSession = useRaceStore((s) => s.setSession);
  const setARISDriver = useRaceStore((s) => s.setARISDriver);
  const arisDriver = useRaceStore((s) => s.arisDriver);

  const [year, setYear] = useState(2024);
  const [rounds, setRounds] = useState<RoundCard[]>([]);
  const [round, setRound] = useState<RoundCard | null>(null);
  const [sessionType, setSessionType] = useState<string>("R");
  const [driver, setDriver] = useState<string>(arisDriver ?? "VER");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState("");

  useEffect(() => {
    getCalendar(year).then((r) => {
      setRounds(r);
      setRound(r.find((x) => x.circuitName === "Netherlands") ?? r[14] ?? r[0]);
    });
  }, [year]);

  useEffect(() => {
    setARISDriver(driver);
  }, [driver, setARISDriver]);

  async function handleLoad() {
    if (!round) return;
    setLoading(true);
    const steps = [
      { pct: 20, label: "Fetching session metadata…" },
      { pct: 45, label: "Loading lap-by-lap telemetry (FastF1)…" },
      { pct: 70, label: "Building circuit map…" },
      { pct: 90, label: `Loaded ${round.isSprint ? "~52" : "~72"} laps, 20 drivers…` },
      { pct: 100, label: "Ready." },
    ];
    for (const step of steps) {
      await new Promise((r) => setTimeout(r, 260));
      setProgress(step.pct);
      setProgressLabel(step.label);
    }
    const meta = await getSession(year, round.round, sessionType);
    setSession({ ...meta, driverCode: driver });
    setLoading(false);
    onLoaded();
  }

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-carbon/95 p-4 backdrop-blur-sm">
      <div className="flex max-h-[92vh] w-full max-w-4xl flex-col gap-6 overflow-y-auto rounded-[8px] border border-border bg-surface p-6">
        <div>
          <h2 className="font-mono-data text-xs uppercase tracking-[0.15em] text-muted">Session selector</h2>
          <h1 className="mt-1 text-2xl font-bold text-white">Load a race to replay</h1>
        </div>

        <div className="flex items-center gap-3">
          <span className="font-mono-data text-xs text-muted">Year</span>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="rounded border border-border bg-carbon px-3 py-1.5 font-mono-data text-sm text-white"
          >
            {YEARS.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        <div>
          <div className="mb-2 font-mono-data text-xs uppercase text-muted">Round</div>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {rounds.map((r) => {
              const pills = sessionPillsFor(r);
              const selected = round?.round === r.round;
              return (
                <div
                  key={r.round}
                  className={`shrink-0 rounded-[8px] border p-3 ${
                    selected ? "border-red bg-red/10" : "border-border bg-carbon"
                  }`}
                  style={{ minWidth: 170 }}
                >
                  <div className="flex items-center gap-2 font-mono-data text-sm text-white">
                    <span>{r.countryFlag}</span>
                    <span>{r.circuitName}</span>
                    {r.isSprint && <span className="rounded bg-amber/20 px-1 text-[9px] text-amber">[S]</span>}
                  </div>
                  <div className="mt-0.5 font-mono-data text-[10px] text-muted">
                    {new Date(r.date).toLocaleDateString()}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {pills.map((p) => (
                      <button
                        key={p.type}
                        disabled={!p.eligible}
                        title={!p.eligible ? "ARIS runs on Race and Sprint Race sessions only." : undefined}
                        onClick={() => {
                          setRound(r);
                          setSessionType(p.type);
                        }}
                        className={`rounded px-1.5 py-0.5 font-mono-data text-[9px] ${
                          !p.eligible
                            ? "cursor-not-allowed text-muted-2"
                            : selected && sessionType === p.type
                              ? "bg-red text-white"
                              : "bg-surface-2 text-white hover:bg-border"
                        }`}
                      >
                        {!p.eligible && "🔒 "}
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <div className="mb-2 font-mono-data text-xs uppercase text-muted">Driver</div>
          <div className="grid grid-cols-4 gap-2 sm:grid-cols-5 md:grid-cols-10">
            {MOCK_DRIVERS_2025.map((d) => (
              <button
                key={d.driver_code}
                onClick={() => setDriver(d.driver_code)}
                className={`flex flex-col items-center gap-1 rounded border p-2 ${
                  driver === d.driver_code ? "border-red bg-red/10" : "border-border bg-carbon hover:border-white"
                }`}
              >
                <span className="h-1.5 w-6 rounded" style={{ background: d.team_colour }} />
                <span className="font-mono-data text-[11px] text-white">{d.driver_code}</span>
                <span className="font-mono-data text-[9px] text-muted">#{d.driver_number}</span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 font-mono-data text-xs uppercase text-muted">ARIS</div>
          <ARISToggle />
        </div>

        {loading ? (
          <div className="flex flex-col gap-2">
            <div className="h-2 w-full overflow-hidden rounded-full bg-carbon">
              <div className="h-full bg-red transition-all" style={{ width: `${progress}%` }} />
            </div>
            <span className="font-mono-data text-[11px] text-muted">{progressLabel}</span>
          </div>
        ) : (
          <button
            onClick={handleLoad}
            disabled={!round}
            className="self-start rounded-[8px] bg-red px-6 py-3 font-mono-data text-sm uppercase text-white hover:brightness-110 disabled:opacity-50"
          >
            Load Session
          </button>
        )}
      </div>
    </div>
  );
}
